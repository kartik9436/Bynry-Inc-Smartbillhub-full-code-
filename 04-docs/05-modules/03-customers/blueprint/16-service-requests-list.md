# 16 · Service requests list EXISTS BEHIND

**Source:** `accounts-blueprint.pdf`, pages 141–242. Extracted text, verbatim — **derived, do not edit.**

**276,949 characters over 102 page(s).**

⚠ **The blueprint prints this entry on the same page as 17 · Service request detail EXISTS BEHIND**, so the text below covers all of them. Read the heading you want.


⚠ **Some of these pages carry little extractable text** (a drawing rather than prose); read the PDF for those.

---

```
History worth knowing A1 has specified five steps since 2026-08-08 and the product shipped three for sixteen days — no column mapping and no value mapping — so a utility whose CSV
did not already use our header names could not import accounts at all. Every gate was green over it, because no gate compares a shipped wizard's step count to the
step list its spec writes for it.
Rules BR-CUS-046 · 047 · 048 · 049 · 050 · 051 · 052 · 075 · 076 · 172 · 672 · 673 · 1041 · 1042 · 1043 · BR-MET-096
16 Service requests list EXISTS BEHIND
/:tenant/requests  ·  S83  ·  also embedded at /accounts?tab=requests with urlState={false}
Drawn with the flow that fills it. The list is beside the six-step capture wizard
in Starting service, so the steps, the queue they land in and the record they
become are read together — jump to it.
How you get here Four doors: the request detail's back crumb and its "Save & exit" (ServiceRequestDetailPage.tsx:1240, :1271), the capture wizard's back crumb
(ServiceRequestCapturePage.tsx:1336), and global search's "View all in Requests" (GlobalSearchResults.tsx:220). Plus the Accounts screen's Requests tab,
which embeds it.
Tabs None of its own. When embedded, ownsUrl=false suppresses only its page header and its URL-backed table state — it touches no row cell.
Write surfaces Detail the row's 👁  Open action links to the request (ServiceRequestsListPage.tsx:415) — in both the standalone and the embedded copy. Note that the
request number IS A LINK to the request as of 2026-09-20 — `DEF-CUS-6005`, `ed11c1b64`, 2.317.2. This sentence read
"the request number is plain text, not a link, so drill-in is via the eye icon only" and that was the defect: the PO
reported *"in list view user cannot click on SR-26-0013 and open it"*. TWO DOORS, ONE DESTINATION now — the reference
carries `data-request-record` and the eye stays, both built from `serviceRequestPath` so they cannot drift. The
blueprint p085 draws the number unlinked beside a labelled `↗ Open` button; B14 rule 15 makes that button an eye here,
so the divergence is stamped at the call site. A request with no number (BR-CUS-093) is NOT wrapped.
Walked Not walked.
17 Service request detail EXISTS BEHIND
/:tenant/requests/:requestId  ·  S84
Drawn with the flow that fills it. The record is beside the six-step capture
wizard in Starting service, so the steps, the queue they land in and the record
they become are read together — jump to it.
How you get here Three doors: the list's 👁  row action, "Open the request" on the capture confirmation (ServiceRequestCapturePage.tsx:1557), and a global-search result row
(GlobalSearchResults.tsx:100).
Write surfaces Update document verification, fee waivers, the decision. A fee line cannot be deleted — it is waived with a reason, the line stays visible and the waiver is recorded
against a name.
Walked Not walked.
Commitments in sections 03–06
ACC-S4
Every date field behaves the same way across the flow
STATUS Unverified
WAITS ON A shared .date-input component, which does not exist anywhere in 07-frontend today — so no screen in the product can satisfy UI-RULES 7, and this is not an Accounts
problem.
SCREENS 03 · 04 · 08 · 10 · 11 · 12 · 13 · 14
WHAT DONE LOOKS LIKE ON SCREEN On the move-out wizard's step 2, the Moved out on field shows 08/31/2026 in the tenant's own format, accepts 08312026 typed straight in, and
offers a TODAY shortcut beside the calendar. It does that identically on all eight screens.
ACC-S5
The catalogue stops carrying sentences no screen shows
STATUS Unverified
WAITS ON Nothing — the conditions these sentences described were all resolved. AccountsListPage.tsx:179 already records that ArrivesWith is no longer imported and that every tab
renders a body; the six tab sentences stayed in the catalogue anyway.
SCREENS 01 (six tab strings) and the account detail (four more)
WHAT DONE LOOKS LIKE ON SCREEN Nothing changes on screen — that is the point. customers.accounts.arrives.moveIns and its nine siblings are gone from all eleven catalogues,
and a grep for accounts.arrives returns nothing outside the git history.
ACC-S6
A hold that has expired goes red instead of going stale
STATUS Unverified
WAITS ON A convention, not a table: when a refusal is written with a clock in it — "in this version", "in this release", "arrives with X" — the same commit adds a test that fails when X lands.
SCREENS 01 · 02 · 03 · 04 · 08 · 12 · 14
WHAT DONE LOOKS LIKE ON SCREEN Seventeen strings in this flow carry such a clock. When the customer portal shipped, the suite went red naming
customers.account.note.customerVisibleInert — rather than that sentence surviving on the Notes tab for a reader to find, which is what happened.
ACC-S7
A close-out has a story that owns it
STATUS Unverified
WAITS ON An epic. The act was ruled by the PO on 2026-08-27 and the screen was built the same day; no epic covers it, and the screen's own trace block says a story is owed.
SCREENS 10
WHAT DONE LOOKS LIKE ON SCREEN Nothing on screen — this one is a record gap, and it is in a commitment card because the alternative is that it stays a comment nobody actions. A
US-CUS story names the close-out, its states and its test cases, and CloseOutPage.tsx's Story line stops reading "NO STORY OWNS THIS SCREEN."
07
Wh t b k h th d t d i
What broke when the product was driven
One row per failure seen in the running app — not per journey and not per
screen.
Correction, applied in place · the app WAS driven, and the reason given for not driving it was mostly wrong
WAS: 0 of 14 journeys walked. No docker socket, no systemd, PostgreSQL not listening, node_modules empty, Django not importable — so nothing could be run.
NOW: the stack was booted and driven. Four of those five reasons did not survive one command each. PostgreSQL 16 was fully installed at /usr/lib/postgresql/16/bin; pip was present;
node_modules is gitignored at .gitignore:8, so npm ci touches nothing tracked; and Docker was never needed — make up is a way to run this product, not the only one. Only "nothing is
listening on 5432" was true, and that is a thing you start, not a blocker.
What was run. PostgreSQL 16.13 on port 5433 · the backend in a virtualenv outside the repository · 334 migrations · seed_demo then load_sample_data --tenant brazosbend,
which wrote 1,647 rows — 72 accounts, 91 bills across two cycles, 40 payments, a live payment plan, a completed move-out, a parked move-in · the front end built and served by
its own server.mjs with /api/* passed through to Django, which is the same-origin shape the product ships. git status --porcelain is empty: nothing in the repository was
written.
What that changes about the rest of this document. The four classes of defect only a driven walk can find were out of reach and are not any more — and one of them was there.
Every drawing in §06 has also been re-measured against the running shell, which is where the Reports nav item, the 240px sidebar, the 40px page title and four wrong wizard
steppers came from.
What broke
Journey Step Screen Did Expected Got Severity
Close-out Open the
close-out
screen
22 ·
/accounts/{id}/close-
out
Opened the
close-out act on
an active
account from
the account
detail
The eligibility
preview — the cut
date, the blocker,
the dunning
consequence
404. The client requests /api/brazosbendaccounts/{id}/close-out — the
tenant segment and the path are concatenated with no separator.
closeOutEndpoints.ts:131 builds `accounts/${id}/close-out` with no
leading slash, and apiPath() returns `${API_PREFIX}/${tenant}${path}`
(client.ts:360). Both the GET preview and the POST commit use that one
builder.
BLOCKS
THE
JOURNEY
Move-out Step 3 — the
settlement
read
08 ·
/accounts/{id}/move-
out
Reached the
step that reads
what the
account owes or
is owed
The close-impact
answer, and the
landing it implies
404, the same fault in a second place: MoveOutWizard.tsx:1166 requests
`accounts/${accountId}/close-impact`, also with no leading slash.
BLOCKS
THE
JOURNEY
Record
payment
The modal's
balance line
and amount
field
02 · /accounts/{id} →
Record payment
Opened the
modal on an
account whose
balance is
$158.10
Two decimals —
$158.10, as the list
and the header
show it
158.100000 USD, and the amount field pre-filled with 158.100000.
AccountActions.tsx:321 interpolates `${balance} ${currency}` raw;
:234 seeds the input from the same string. Hard rule 2 says money
DISPLAYS 2.
BREAKS A
HARD
RULE
Accounts
list
Default
ordering
01 · /accounts Opened the list
with nothing
chosen
The work a clerk
has just created, at
the top
Sorted alphabetically by name, ascending — ?sort=name&dir=asc is sent
before the clerk touches anything. A newly created account lands wherever
its customer's surname falls, which on this tenant is page 2 of 2.
WRONG
BY DESIGN
Accounts
list
The two
uncounted
01 · /accounts Read the KPI
band against a
A count, or an
honest absence
PAST-DUE 60+ and CLOSED THIS YEAR both read “Not counted yet” while
the table on the same screen shows two accounts past 60 days and the
HONEST,
STILL
list uncounted
tiles
band against a
tenant that has
61–90 and 90+
rows in the
table below it
honest absence the table on the same screen shows two accounts past 60 days and the
estate contains a closed account. Deliberate and documented
(AccountsListPage.tsx:673–686) — but the reason is a gap, not a ruling,
so it is a specification and not out of scope.
STILL
OWED
The two 404s are one defect, and it is the kind nothing in this repository could have caught
Every other API path in 07-frontend/src begins with a slash — "/ledger/accounts", "/jobs", "/finance/cost-of-service". Exactly two do not, and both are in this module: the
close-out pair and the move-out settlement read. Concatenated with the tenant segment they produce /api/brazosbendaccounts/…, which is a real URL shape, so nothing throws —
the server simply answers 404 and the screen shows its could-not-load state.
Proved against the running server rather than argued, both paths side by side on the same session cookie:
Requested Status Body
/api/brazosbendaccounts/{id}/close-out — as built 404 Django's "Page not found" HTML
/api/brazosbend/accounts/{id}/close-out — one character 200 {"account_no":"AC-2026-00001","eligible":false,"blocked_by":{…
/api/brazosbendaccounts/{id}/close-impact — as built 404 Django's "Page not found" HTML
/api/brazosbend/accounts/{id}/close-impact 200 {"currency":"USD","landings":["settled","refund_due","short",…
Why no check saw it. A unit test mocks the client, so the path never reaches apiPath(). tsc sees a well-typed string. The backend's own tests call the view directly. And hard-won
law 7's shape applies: the front-end test asserts the wrapper was called, which is true. Only a request made by a browser against a real server can see this, and that is the one
thing the previous version of this document had not done.
What worked, said plainly — an empty failure list is worth nothing without it
Walked Did Saw
Sign-in →
Accounts
Signed in as the seeded owner and
landed on the list
72 accounts, $24,992.65 outstanding, 1 pending activation. No console error, no failed request.
The eight list
tabs
Clicked every tab All eight render, each reflects in the URL as ?tab=…, each swaps the primary action to its own (+ New request, + New connect, Start a
disconnect, ↑ New import). Rows: 72 · 6 · 8 · 1 · 1 · 0 · 6 · 3.
Search Typed a name, then an address,
then nonsense
Server-side every time — ?q=Bramble returns the one bakery, ?q=44+Larkspur matches on address, nonsense returns zero rows
rather than an unfiltered page. This corrects an earlier probe of mine that filled the topbar's global search by mistake and reported
search dead.
Sort and
paging
Sorted on balance, then paged Both are server parameters — ?sort=balance&dir=asc and ?page=2&per=50, which returned the remaining 22 rows. Four headers
sort (Account, Name, Balance, Status); the per-page control offers 50/100/200/500/1000.
Account detail,
all 12 tabs
Opened a row and clicked every
tab
Overview · Bills · Payments · Credits · Payment plan · Usage · Meters · Work · Adjustments · Documents · Notes · Audit. All twelve
render, all twelve reflect in the URL, none is blank, none raised an error. The header composes 101 Silver Creek Rd · Unit 1 · Silver
Creek, TX 78611 — the walk to premises works.
R d O d h d l d Th i j lk d i d l l d d h i i h
Record
payment, end
to end
Opened the modal, entered
$25.00, submitted
The one write journey walked to a commit. POST /api/brazosbend/accounts/{id}/payments, modal closed, and the row is in the
database — 25.000000 against that account. The path is correct here, which is what makes the two 404s above a local fault rather
than a systemic one.
Six wizards
opened
Opened New account, Import,
Service request, New connect,
Transfer, Disconnect
All six boot and draw their rail. Step counts confirmed: 6 · 5 · 6 · 9 · 5 · 5.
What is still NOT walked, and it is named rather than left to look complete
Six of the fourteen in-scope journeys were opened but not completed to a commit. Every wizard above was driven to its first step and its rail read; none was driven through to
the write, because each needs data the walk would have had to author — a vacant unit for a move-in, an unbilled cycle for a move-out. Those steps are drawn in §06 from the code,
and they are read, not seen. The distinction is the whole point of this section, so it is kept even where it is unflattering.
And two steppers could not be confirmed at all. Change plan and Payment plan draw three steps each in §06; the running product shows no rail on either entry screen, only a
disabled Continue. Either the rail appears once the first choice is made, or the drawn stepper is wrong. This document does not know which, and says so rather than guessing — it is
the one place in §06 where a drawing is unverified against the screen.
08
Every stated absence, and its one decision
Built from the product's own user-facing copy — the sentences a person reads
when something cannot be done — not from an auditor's impressions and not
from the design, which is a proposal and therefore the wrong place to look for
what the server can serve.
The contrast, stated as counts
The wireframes in the design state zero absences. The product's own copy for this flow states 131, of which 57 hold a control the user can see and cannot use. A further 14 are
dead copy — present in all eleven catalogues, rendered by no source file at all — and 17 are rotting holds, refusals written with a clock in them that nothing re-checks.
The judgement rule, applied without exception: a recorded ruling that a thing waits makes it out of scope, with the ruling quoted. No ruling makes it a specification naming
what it waits on.
The borderline case, and how the rule decided it. The accounts search placeholder reads "Account #, customer #, name, address, or meter #…" where UI-RULES 19 says prompts
read "Search {entities}…". That looks like a violation. It is not: B14's own amendment records this exact case — five prompts read a bare field list because those sentences are served
verbatim by the server as search.hint, and rewriting them by lane fiat would put the drawn prompt and the served hint into disagreement. It is OQ-600, open, put to the PO as a
copy call. So: out of scope, with the ruling quoted — not a defect, and not this document's to decide.
The absences that hold a control — the worst kind
What is absent Screens Decision Reason, and who ruled it
Adjust — "Adjustments are billing rows, and billing is not built. There is no endpoint to post
one to."
02 OUT OF
SCOPE
Billing's own module is unbuilt. No ruling is needed to defer a
screen to a module that does not exist.
Send statement — "Statements are not built yet." 02 OUT OF
SCOPE
Same. The one permanently dead glyph on the rail.
Print bill — "No bill has been issued yet." · Issue credit — "A credit needs an issued bill." 02 OUT OF
SCOPE
Not a build gap at all — a state gate. Both navigate once a bill
exists. See the correction below.
Upload a document — "Nothing stores a document yet: there is no upload endpoint and no
table behind it."
02 ACC-S8 No ruling defers it; BR-CUS-036 names the table and it was never
built. A specification.
Update payment method — "…belong to payments, which keeps none for an account in this
version."
02 OUT OF
SCOPE
BR-CUS-059 rules autopay capture-only in v1. Ruling quoted, thing
deferred.
Move-out / Move-in / Change plan / Payment plan / Activate / Close out, each disabled
on the wrong account state
02 OUT OF
SCOPE
Not absences at all — correct state gates, each naming the rule that
refuses (BR-CUS-017, 018, 030, 430). Listed so the count is honest.
Reopen a finished import run — "Reopening a finished run is not switched on yet." 15 ACC-S9 No ruling. A specification.
Restrictor instead of a full cut — "This product knows cut and not-cut, and a restricted
service is neither… What a restricted service is charged has not been ruled, and that price is the
blocker."
12 OUT OF
SCOPE
Blocked on a PO ruling that has not been made. The copy names
the blocker itself.
The earliest lawful cut date — "…is not computed anywhere in this product… so this screen
cannot stop an unlawful date being chosen here."
12 ACC-S10 No ruling defers it, and the consequence is legal rather than
cosmetic. A specification.
Correction, applied in place · the icon rail is not what its own docstring says
WAS: four of the seven rail glyphs are dead — Send statement, Print bill, Issue credit, Disconnect notice — and three are live.
NOW: six of seven are reachable. Print bill and Issue credit are state gates that navigate once a bill exists (accountRailReadiness.ts:227, :257); Disconnect notice navigates to
/disconnects/new?account=<id> (:291). Only Send statement is permanently dead.
The docstring is the stale part. AccountIconRail.tsx:59 still reads "Three are LIVE (Change plan · Payment plan · Add note)", while accountRailReadiness.ts — added by DEF-CUS-
4631 — moved the refusals to state gates. Hard-won law 1: a comment claiming a guarantee is not the guarantee. This audit's own first pass repeated the docstring before
reading the readiness module; the row is struck rather than deleted so the next reader sees why.
Dead copy — 14 sentences no screen shows
Each is present in all eleven catalogues and referenced by no non-test source
file. The condition each described was resolved and the wording was never
removed.
Key What it says Why it is dead
customers.accounts.arrives.requests
…moveIns · …moveOuts
…newConnects · …transfers
…disconnects
Six sentences saying each
worklist tab "arrives later".
All six tabs were built. AccountsListPage.tsx:179 records the milestone in its own words —
"`ArrivesWith` IS NO LONGER IMPORTED, AND ITS ABSENCE IS THE MILESTONE… every tab on this screen
renders its contents rather than a note about itself" — and the six strings stayed in the catalogue.
customers.accounts.arrives.requestsBuilt "Showing that list inside this
tab is still to come; the button
The list is embedded in the tab now (DEF-664).
tab is still to come; the button
takes you straight to it."
customers.account.arrives.customer
…customerTitle
Two sentences about the
shared customer record.
The customer entity was built; the panel renders live links.
customers.accounts.awaits.billing
…billingTitle · …other · …otherTitle
Four sentences about what the
list is waiting on.
Superseded by the per-cell absences the KPI strip and the cells now carry.
customers.moveOut.shortfall.absent "…None of them is offered yet,
because nothing accepts the
answer."
Both unrendered and no longer true. The four shortfall paths were mounted — POST
/accounts/{id}/settle-shortfall — and the wizard renders shortfall.unread instead.
Rotting holds — 17 refusals with a clock in them
A hold is correct the day it is written and rots on the day the thing it refused
arrives, because landing a feature and releasing the sentence that pointed at it
are two acts and only the first feels like the work.
The hold Its clock Status
customers.account.note.customerVisibleInert "there is no customer portal in this version" EXPIRED AND STILL ON SCREEN — 155 files under src/portal/. Rendered at
AccountActions.tsx:516.
customers.account.audit.portalActorWhy "There is no customer portal in this version" EXPIRED AND STILL ON SCREEN — rendered at accountDetailTabs.tsx:1180.
customers.moveOut.impact.notServed "arrives with the close-impact read, which is
not built yet"
EXPIRED — the read is mounted; GET /accounts/{id}/close-impact answers.
customers.account.pill.autopayOnWhy
…newAccount.preferences.autopayHint
…moveOut.impact.payments.autopayExplicit
"nothing collects on it in this version" × 3 STILL TRUE — BR-CUS-059 rules autopay capture-only in v1.
customers.moveIn.send.absent
customers.paymentPlan.queueOnly
customers.disconnect.step3.channelBlocked
customers.disconnect.step5.sendBlocked
"in this release" × 4 STILL TRUE — notifications has no tables.
⚠ AMENDED 2026-09-24 (DEF-CUS-6365). `customers.moveIn.send.absent` is RETIRED —
the key no longer exists in any of the eleven catalogues and nothing renders it.
The move-in review draws blueprint p077's *What goes out* table in its place, one
row per message the save really queues, read from the utility's own notification
rules. The verdict beside it was also wrong by the time it was written:
notifications HAS tables — `outbound_messages` holds 372 rows on the sample
tenant — and "in this release" is about DISPATCH, which is `BR-NOT-013` and is
still true. The other three keys are untouched by this lane.
customers.newAccount.deposit.arrives "arrive with the deposit work" STILL TRUE — names a wave with no date and nothing re-checking it.
Commitments in this section
Three absences carry no ruling that defers them, so each is a specification
naming what it waits on. Everything else in the tables above is out of scope with
its ruling quoted.
ACC-S8
An account can hold a document
STATUS Unverified
WAITS ON The table BR-CUS-036 names and an upload endpoint. The product's own words are the blocker: "Nothing stores a document yet: there is no upload endpoint and no table
behind it."
SCREENS 02
WHAT DONE LOOKS LIKE ON SCREEN The Documents tab lists Tenancy agreement · Contract · 12/03/2026 · S. Miller · 214 KB instead of drawing headings over a stated absence, and
UPLOAD is not disabled.
ACC-S9
A finished import run can be reopened to fix its rejected rows
STATUS Unverified
WAITS ON Nothing ruled. The copy says only "Reopening a finished run is not switched on yet. Correct the file and import it again."
SCREENS 15
WHAT DONE LOOKS LIKE ON SCREEN On a run reading 1,966 loaded · 34 rejected, a FIX ROWS action opens those 34 with their reasons; correcting and re-committing moves the run to
2,000 loaded · 0 rejected.
ACC-S10
A cut cannot be scheduled before it is lawful
STATUS Unverified
WAITS ON The notice date plus the statutory period, rolled forward past weekends and public holidays. The screen says nothing performs that roll: "…so this screen cannot show it and
cannot stop an unlawful date being chosen here."
SCREENS 12
WHAT DONE LOOKS LIKE ON SCREEN Disconnect step 3 shows Earliest lawful cut date: 05/14/2026, and the picker refuses anything before it with the reason visible on the disabled cells.
ACC-S18
A company customer is opened under the master account that owns its building
STATUS Unverified
WAITS ON A search that narrows the account list to master accounts and answers on company name, account number and service address — all of which the published list already takes.
Nothing is waiting on a rule: the second half is a decision, not a gap, and it is named in the row below.
SCREENS 03 · step 1
WHAT DONE LOOKS LIKE ON SCREEN Choosing Company opens a search under it, and picking a row fills the association. A company that rents its premises shows Not associated with a
master account pre-selected with the reason beside it, and the account opens normally — an empty result reads differently from a company that has none at all.
THE OPEN HALF, STATED RATHER THAN ASSUMED Where the association is STORED was never decided. It is drawn as a choice a clerk makes and the product has no column for it, so
this commitment covers the search and the screen, and not the writing.
ACC-S19
A clerk is told, while they are typing, that this customer is already on file
STATUS Unverified
WAITS ON A read that judges a block of details WITHOUT writing anything. The criteria are ruled, the evidence is stored and encrypted with a one-way token beside it, and one function
already resolves the party for four doors and answers linked, created or none — but it answers at SAVE, and drops the word before any screen sees it. Nothing here needs a matcher built.
SCREENS 03 · step 2  ·  04 · step 2  ·  06 · step 1
WHAT DONE LOOKS LIKE ON SCREEN One panel, headed This looks like somebody you already have, on all three doors, with the candidates, what agreed and what did not, and a dialog
that opens over the form showing the accounts, the deposit and the history. Nothing is preselected. On the service request the link button is greyed with its reason, because that door
creates no customer.
WHAT IT IS WORTH One landlord in this system holds three customer numbers. A customer who has been here before is asked for a second $150.00 deposit while the utility is already
holding theirs.
09
Where the screens depart from the rules
Judged against B14 first, r10 second, in that order. One row per violation, never
per screen. Most of B14 is ratified and unenforced — no gate in this
repository reads rendered output — so a green suite is evidence of nothing
here, and the last column is the point of the table.
Screens Rule What it says What the screens do Where Enforced?
03 · 04 · 08 ·
10 · 11 · 12 ·
13 · 14
UI-
RULES
7
"Every date uses .date-input
(calendar affordance, MM/DD/YYYY
keyed entry, Today shortcut). Never
a bare text input."
There is no .date-input component or class anywhere in 07-frontend — a
grep returns nothing outside test files. Every date in these flows is a native
<input type="date">: no Today shortcut, and the displayed format follows the
browser locale rather than the tenant's, while DateCell everywhere else formats
per tenant.
UI-RULES.md:16
CloseOutPage.tsx:218
+ 7 more
RATIFIED,
UNENFORCED
In fairness to the screens: a native date input is timezone-free, so the hazard
that usually bites date fields — a timestamp rendered in the browser's zone
showing the previous day for every user west of the server, which on a billing
product is a bill dated a day early — does not bite here. The violation is the
missing Today shortcut and the locale-dependent format, not a wrong date. And
the rule is repo-wide rather than an Accounts failing: the component it names
was never built.
Checked and found compliant
Rule Verdict Evidence
UI-RULES 14 column selector PASS Show/hide, bidirectional reorder, Reset, and persisted per user server-side under table.<screen>.columns. The identity column can never be
hidden. DataTable.tsx:120, :381, :742
UI-RULES 16 pagination footer PASS On the response. core/pagination.py:34 — but see the NFR-3 finding: the response pages and the work does not.
UI-RULES 17 empty state PASS All ten tabs render a real list with an empty state and a CTA. None renders a note about itself.
UI RULES 11 PASS M t t 5 ( i l ) Di t t 4 ("Wh t thi ill d / ill t d ") Cl t ("Wh t thi ill it ") N t t 6
UI-RULES 11 consequence
preview
PASS Move-out step 5 (nine panels) · Disconnect step 4 ("What this will do / will not do") · Close-out ("What this will write") · New account step 6
("What this create will not write").
B14 rule 6 danger tier PASS Close-out and Schedule the disconnection both take the danger tier; the ⚡  rail glyph carries it too.
B14 rule 31 no database id on
screen
PASS Every identity cell renders account_no, not the UUID. The account header composes its locality by walking to the premises rather than reading a
retired address kind.
Exempt — not violations
Screen Rule Why it is exempt
01 UI-RULES 19 · search
placeholder
OQ-600, open. B14's own amendment names this exact case and the reason: the sentence is served verbatim by the server as search.hint, and rewriting
it by lane fiat would put the drawn prompt and the served hint into disagreement about one box. 14-ui-conventions.md:205-211
02 UI-RULES 15 · row actions
capped at two
The seven-glyph rail is not a row-actions cell. RowActions is flex-nowrap for a table column (DEF-352); this is a wrapping rail under a rule, and the
divergence is stamped in the file.
10
The remedies, drawn
Every element numbered, every number given a line: what it is · where its data
comes from · which rule it satisfies · new, changed or unchanged. That last
field is what makes the drawing diffable against the screen it replaces — without
it a reader cannot tell the fix from the redraw, and a remedy nobody can diff
gets built whole.
Two constraints that bind every drawing below
Rule 21. AccountsListPage.tsx, AccountDetailPage.tsx, NewAccountWizard.tsx, ChangePlanWizard.tsx, PaymentPlanWizard.tsx, AccountActions.tsx and customersShared.tsx are
not on 07-frontend/src/styles/route-b-migrated.txt. A Tailwind utility written in any of them renders as nothing at all, and tsc, eslint and every toContain("flex") assertion
pass on it. So R1 below reuses classes customers.css already declares, or lands in a sibling file that is on the list — which is exactly how accountDetailHeader.tsx,
accountDetailTabs.tsx and AccountIconRail.tsx came to exist.
A drawing is not a commitment. These are descriptions until they appear in a commitment card in §12.
R1 · An Edit form on the Account panel ACC-S1
/brazosbend/accounts/a-10432?tab=overview&edit=account
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Accounts / A-10432 ⚲  Search accounts, premises, meters… ⚑ ?
▦
←  Account A-10432
ACCOUNT A-10432 · MILLER, SARAH
Accountdetails
1. ①  Account panel heading · unchanged · customers.css panel class · UNCHANGED
2. ②  Edit control · opens the form in place · UI-RULES 4 (Verb → grammar; here a pencil per rule 15's icon vocabulary) · NEW
3. ③  Category select · value ← accounts.account_type; options ← the fetched platform catalogue (useAccountCategories, already on this screen for the list filter) · UI-RULES 8 · NEW
4. ④  Preferred language select · value ← accounts.preferred_language; options ← NOT SERVED — the copy already admits it: "No screen lists them yet, so the server checks what you type." This one line
makes R1 a back-end change wearing a wireframe · UI-RULES 8 · NEW
5. ⑤  Tax-exempt expiry · value ← accounts.tax_exempt_expires · UI-RULES 7 — drawn as the .date-input the rule names, with the Today shortcut, not the native input the rest of the flow uses · NEW (and
depends on ACC-S4)
6. ⑥  Save · PATCH /accounts/{id} → services.update_account, already built, audited and tested · UI-RULES 4 (Verb ✓ commits) · NEW WRAPPER, EXISTING ENDPOINT
7. ⑦  Read-only notice · states which fields the server refuses and why · BR-SHL-025 · NEW
Where this lands. AccountDetailPage.tsx is legacy CSS, so the form goes in a
sibling on the migration list — the same move accountDetailHeader.tsx made
— or reuses customers.css's existing classes. Drawn either way, it must not
introduce a utility into the parent file.
R2 · A list footer that is honest about what it sorted ACC-S2
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
Account details
Editing · the rest of the page is unchanged behind this panel
①  ACCOUNT
③  Category *
Residential ▼
Sub-type
Single family ▼
④  Preferred language
English ▼
The accepted codes come from this utility's regional settings.
TAX EXEMPTION
✓ Tax exempt
Reference
TX-EX-99213
⑤  Expires
12/31/2027 📅
Today · MM/DD/YYYY · tenant time (America/Chicago)
⑦  Unit, account type and status are not editable here — a unit never moves, and
closing an account is its own flow rather than an edit here.
Cancel ⑥  Save changes ✓
/brazosbend/accounts?tab=accounts&sort=balance&dir=desc&page=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Accounts ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
CUSTOMERS
Accounts
+ New account
Filter ▾ ⚲  Search by account, name or address Columns ▾ ⇩  Export
ACCOUNT ⇅ NAME ⇅ BALANCE ⇅ AGEING
A-11488 Reyes, T. $612.75 90+
A-10432 Miller, Sarah $247.30 31–60
⑧  Showing 1–50 of 40,000 · Rows per page 50 · ⇤  ←  Page 1 of 800 →  ⇥
1. ⑧  Pagination footer · count from the DRF envelope · UI-RULES 16 · UNCHANGED
2. ⑨  Sort scope line · states whether the ordering is over the whole result set or only the page · no rule covers this — it is stated only in this document, and appendix A counts it as a NO HOME · NEW
Why the remedy is one sentence and not a redesign. The real fix is server-
side and is a decision, not a drawing: either the derived positions get
materialised somewhere sortable, or the list sorts in SQL on the four stored
columns and says so. Drawing a new toolbar here would be a redesign wearing a
fix's clothes — the maintenance process names that case explicitly, and it has
already gone wrong once on the property Overview. ⑨  is the only element this
remedy adds.
R3 · One date control, everywhere ACC-S4
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
▤
▧
✦
▩
▦
▤
⚙
⑨  Sorted by Balance across all 40,000 accounts
/brazosbend/accounts/a-10432/move-out?step=2
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
v2.234.15
Account A-10432 / Move-out ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Account A-10432
MOVE-OUT
Date & final reads
Step 2 of 6 · Date & final reads
✓ Find account 2 Date & final read 3 Final bill & deposit 4 The shortfall 5 What happens next 6 Review & close
⑩  Moved out on *
08/31/2026 📅
⑪ Today  ·  ⑬  MM/DD/YYYY — type it or pick it · interpreted in the tenant's timezone, America/Chicago
August 2026   ‹ ›
Su Mo Tu We Th Fr Sa
… 24 25 26 27 28 29 30
31 1 2 3 …
⑫  Dates before 01/29/2026 are unavailable — the outgoing account must be billed through the move day.
FINAL READS
METER READ EST?
M-4021 51,776 ☐
M-4022 1,388 ☐
←  Back Continue →
1. ⑩  The .date-input itself · value ← the wizard's own draft state · UI-RULES 7 · CHANGED — replaces a native <input type="date">
2. ⑪  Today shortcut · the tenant clock, not the browser's · UI-RULES 7, the clause the current control misses entirely · NEW
3. ⑫  Disabled dates with a visible reason · min ← the served earliest_start · BR-CUS-056 · NEW — a cell that will not click and does not say why is a support call
4. ⑬  Format and timezone, stated · format ← the tenant's regional settings, already published by ShellWithSession and read by DateCell · UI-RULES 7 · NEW
One honest note on ⑬ . The current native input is timezone-free, so this
remedy must not introduce a timezone bug while fixing a format one. A date
field whose source is a plain date stays a plain date; the tenant zone is stated so
a reader knows which clock Today means, and for no other purpose.
ACC-S11 · The list opens on the alphabet, and the clerk's own work is what they came for
Seen, not reasoned. Opening /accounts with nothing chosen sends ?sort=name&dir=asc before the clerk touches a control. On the seeded tenant that puts Ana Alvarez first and an
account created a minute ago wherever its customer's surname happens to fall — for half the alphabet, that is page 2.
The ruling, verbatim, PO 2026-09-10: "Whenever any account is created or any entry is created in the system, it automatically sorts it by the alphabetical order. It should always sort
it by the creation order. The new newly created entries should always show on the top."
It is not one list. The sentence says any entry, so the same default is owed by the seven sibling tabs on this screen — Requests, New connects, Move-ins, Move-outs, Transfers,
Disconnects, Imports — and by every list in the product that opens on a name. This document can only speak for the Accounts menu; the rest needs the same walk.
What it costs to build, and the trap in it. The default becomes created_at descending, and the clerk's chosen sort must still win and still survive a refresh. ⚠  The sort happens in
Python today — account_list materialises every matching row with list(qs.order_by("id")) (selectors.py:2751) and then sorts the list (:2803–2814), so a new default is one
more branch in the same in-memory sort rather than an ORDER BY. It will work at 72 accounts and it is the fifth NFR-3 breach either way — see §04. Fix the default and the ordering
together, or the fix makes the breach a little worse and hides it behind a feature.
Routing. Ambiguous between a defect and a change, and 13-change-process.md §1 settles ambiguity the same way every time: it is a defect — "filing our misunderstanding as a
'change' quietly converts our error into the customer's new requirement".
⚠  This ruling is not in the repository. It exists in this document and in the chat that produced it, because the session was scoped to analysis with no repository writes. Law 9 wants
it in 12-governance/02-decision-log.md and in 04-docs/05-modules/08-customers/02-business-rules.md the turn it was made. Until it is there, the next agent will not find it.
ACC-S12 · One missing slash, two dead paths — and it is a one-character fix
closeOutEndpoints.ts:131 and MoveOutWizard.tsx:1166 each build an API path with no leading slash, so apiPath() welds it to the tenant segment and the request 404s. Both were
proved against the running server in §07: the as-built path returns Django's 404 page, the same path with one slash added returns 200 and real JSON.
The fix is /accounts/… in two files. The part worth more than the fix is the guard: nothing in this repository can currently fail on a malformed path, because a unit test mocks the
client and tsc sees a well-typed string. A check that every literal handed to client.get/post/patch/delete begins with / or resolves to a constant that does is a grep, it would
have gone red on the day either line landed, and it is the thing to build alongside the two-slash fix — hard-won law 7: prove it red on these two lines first.
ACC-S13 · Six decimals of money on the screen that takes money
Seen, not reasoned. The Record payment modal shows 158.100000 USD and pre-fills the amount box with 158.100000. Hard rule 2 is not ambiguous — money is stored to 4
decimals and displays 2, re-signed by the PO on 2026-08-22 in the words "MOney 4 decimal, percentage 6 decimal, display both 2 decimal".
It is not a missing feature. The formatter exists, is shared, and is used by every other money surface in the product — MoneyCell.tsx:168, whose own comment reads "BR-TEN-
080: exactly 2 dp on screen". The very same balance renders correctly as $158.10 in the accounts list and in the account header. Two lines in one file bypass it:
 i t l t th t i d d th i t f it
SO
Sam Ortiz
Billing Clerk
AccountActions.tsx:321 interpolates the raw string, and :234 seeds the input from it.
⚠  The reason it reads as deliberate. formatMoney's fallback for an amount it cannot parse is return `${amount} ${currency}` — byte-identical to what line 321 hard-codes. The
modal permanently renders the formatter's error path in place of its normal one, so a reviewer reading the code sees a shape the codebase genuinely contains elsewhere and moves
on.
The consequence is not cosmetic. The pre-filled value is what a clerk submits when they accept the default, so a six-decimal string is what reaches POST /accounts/{id}/payments
on the common path. The fix is formatMoney(balance, currency) for the display and a 2-dp value for the input default. The guard worth more than the fix is a check that no
money-carrying JSX interpolates an amount without going through the shared formatter — it would have gone red the day this line landed, and hard-won law 7 says prove it red on
this line first.
11
R4 · Every quick action as a modal form, open over the account NO COMMITMENT
Thirteen quick actions, thirteen dialogs, every field on one surface. Asked
for directly: "build the modal form for the quick actions. And the wireframe show
the full screen, and in the screen show the model form open. Show all the form
details. each and every quick action should show in the model form with proper
fields and details."
Why a dialog rather than a page, and it is one reason. Nine of the thirteen
take the clerk off the account today — four to a wizard of their own, three to
another module, two to a page that replaces the screen. The clerk is usually on
the phone. What is behind the form is half of what they are being asked about
— the balance, the status, the plan, the tabs — so the page below is dimmed
and still readable rather than replaced, and closing the dialog costs nothing.
Issue credit is the clearest case: as built it leaves for another module and drops
the account on the way, so the clerk is asked to paste a bill id they were one
click from.
Every drawing carries the whole form, not a first step. Where an action has
steps the rail stays for orientation and the fields are all shown at once under the
step each belongs to, ending in the recap. Six of the thirteen are multi-step
today and a reader of the as-built drawings can only see step 1 of each; these
show the other forty-one fields.
What is drawn here that the product does not do yet, each named on its own
drawing: a confirmation on Activate account, which today commits on the click;
a unit search on Move-in, which today has no picker at all; the late fee, the
credits, the allocation and the outstanding remainder on Record payment,
which today shows none of the four; the bill carried across to Issue credit; and
on every one of the thirteen a last step that recaps what was entered. A
control the deployment cannot honour keeps its form and disables its commit
with the reason on it — Adjust, Send statement and Payment plan are all drawn
that way.
y
A drawing is not a commitment. These are descriptions until they appear in a commitment card in §12 — ACC-S14 below is that card.
Quick action 1 of 13 · Adjust · /brazosbend/accounts/a-11812 · the form the product needs before the endpoint exists — commit disabled, with the reason on it
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Adjust this account
Bramble Bakery · A-11812 · balance $2,410.00
✕
WHAT IS BEING ADJUSTED
Adjust what *
This account’s balance ▼
This account’s balance · A specific bill · One line of a bill.
Which bill
Not applicable
There are no bills on this account to adjust.
THE MONEY
Which way *
Credit the customer ▼
A credit reduces what they owe; a debit increases it.
Amount *
410.00
Cannot exceed the balance of $2,410.00.
Tax
No tax ▼
Follow the original line · No tax · Tax at today’s rate.
Effective date *
09/11/2026 📅
The day this counts from.
WHY
Reason *
The opening balance was wrong ▼
The opening balance was wrong · Billed in error · Meter fault · Goodwill · Leak allowance · Rate
applied wrongly · Missed charge · Theft restated
Case or reference number
Whatever the customer can quote back.

This is the account that shows why it matters. The $2,410.00 was carried in as an opening figure with no bill behind it. If any of it is wrong — and two dunning notices have already gone out on it — there is no way to
correct it from anywhere in the product.
Quick action 2 of 13 · Move-out · /brazosbend/accounts/a-11812 · six steps, every field on one surface — including the one the product cannot ask for here
v2.234.15
SO Sam Ortiz
Billing Clerk
Note to the file
Kept with the adjustment and read by anyone asking why later.
APPROVAL
Raised by
Sam Ortiz · Billing Clerk
Approved by
Needs a supervisor ▼
An adjustment over $100.00 cannot be posted by the clerk who raised it.
What this does to the account
Balance now $2,410.00
Where it came from An opening figure, not a bill
This adjustment −$410.00 credit
Days past due 62 — unchanged by a credit
Balance after this adjustment $2,000.00
Every money action writes the audit log. Cancel
Post adjustment
ACC-Q01
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Move this account out ✕

Move this account out
Bramble Bakery · A-11812 · 142 Bakers Row · Suite 1
1 Who & when 2 Final read 3 Bill & deposit 4 The shortfall 5 Address &
unit 6 Review
1 · WHO IS LEAVING, AND WHEN
Account
A-11812 · Bramble Bakery
Fixed by the account you came from.
Move-out date *
09/30/2026 📅
The last day they are responsible for service at this address.
2 · THE FINAL READ
THERE IS NO METER TO READ
Two services have been open at this unit since September 2024 and no meter has ever been fitted. A final read cannot be taken, and the wizard must say so rather than ask for a
number nobody can supply.
Instead of a read *
Close the services without one ▼
Close the services without one · Raise a job to fit and read a meter first · Estimate the period
Services close on
09/30/2026 📅
Defaults to the move-out date.
3 · THE FINAL BILL AND THE DEPOSIT
Final bill
Do not raise one ▼
Raise it on the next run · Raise it now · Do not raise one.
Deposit on file — $0.00
Nothing to settle ▼
Apply it to the final bill · Refund it in full · Hold it
4 · WHAT IS STILL OWED
Balance today
$2,410.00
An opening figure.
How old
62 days past due
Served by the account and shown nowhere on the detail screen.
What happens to the shortfall *
Send it to collections ▼
Keep chasing it · Send it to collections · Write it off (needs a supervisor)
Payment in flight
$500.00 · Processing
PY-260911-0076 has no clearing date, so it has met nothing.
5 · WHERE THE LAST LETTER GOES, AND WHAT HAPPENS TO THE UNIT
Forwarding address
Leave it blank to keep sending to the service address.
Town or city
State ZIP
The unit becomes
Vacant ▼
Vacant · Handed straight to a named next occupant
Letters to send
Close-out letter only ▼
Final bill and deposit statement · Close-out letter only · None
6 · REVIEW — EVERYTHING ABOVE, ONCE MORE
What pressing the button will do
Move-out date 09/30/2026
Final read None — the unit has no meter
Final bill Not raised
Quick action 3 of 13 · Activate account · /brazosbend/accounts/a-11812 · the confirmation the product is missing, and it names the partial failure before the click
v2.234.15
SO
Sam Ortiz
Billing Clerk
Deposit $0.00 — nothing to settle
Shortfall $2,410.00 — sent to collections
Payment in flight $500.00 stays in Processing
Disconnect case DSC-26-0003 Still open
The unit Becomes vacant on 10/01/2026
Account status after this Closed
Save & exit Cancel Move this account out
ACC-Q02
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Activate this account
Kwan, Michael · A-12048 · 88 Pine Vista · Unit 2
✕
Today this commits the moment it is clicked, with no dialog and no way back.
WHEN SERVICE STARTS
Activation date *
09/11/2026 📅
The day the account starts being billable.
Opening read
Use the last read on the meter ▼
Use the last read on the meter · Enter one now · No read needed
Electric starts
09/11/2026 📅
Water starts
09/11/2026 📅
THE PLAN

Quick action 4 of 13 · Move-in · /brazosbend/accounts/a-11812 · the unit is searched and chosen, and everything held about it is shown before the customer is asked for
v2.234.15
SO
Sam Ortiz
Billing Clerk
The unit’s plan
SCW-RES · Sample — Residential · v1
In force at this unit since 06/01/2026.
Base charge
$20.00 a month
There is nothing to pick here: a plan belongs to the unit, and the account inherits it.
THE DEPOSIT
Deposit
Charge the scheduled amount ▼
Charge the scheduled amount · Charge a different amount · Waive it (needs a supervisor)
Amount
150.00
From the plan’s deposit schedule.
Due
08/22/2026 📅
Falls on the first bill’s due date.
Billing cycle
Silver Creek — monthly ▼
Taken from the unit; change it only if this account bills on another round.
TELLING THE CUSTOMER
✓ Send the welcome pack
Send the deposit notice separately
Both are recorded whether or not they can be delivered yet.
REVIEW
What pressing the button will do
Status Pending activation →  Active
Service starts 09/11/2026 · Electric and Water
Opening read Taken from the meter’s last read
Plan SCW-RES v1, inherited from the unit
Deposit $150.00, due 08/22/2026
Cycle Silver Creek — monthly
Two things the server will not manage, and says so now rather than after.
No plan snapshot is recorded — the table that ties an account to a plan version does not exist, so this account will read its plan from the unit.
No deposit is applied — the schedule lookup is not built, so the $150.00 above is recorded as intended and not charged.
Cancel Activate account
ACC-Q03
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Adjust
Activate account
Move-in
Close out
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
▤
▧
✦
▩
▦
▤
⚙
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
✉
🖨
$
Move a new occupant in
Starting from AC-2026-00042, which has just left this unit
✕
1 Find the unit 2 Customer 3 Start & read 4 Deposit 5 Review
1 · FIND AND CHOOSE THE UNIT
Search for a unit *
mill pond
Type an address, a unit label or a premises name.
UNIT ADDRESS TYPE SERVICES VACANT SINCE
Apt 102 301 Mill Pond Ln Apartment ELECTRIC WATER 08/01/2026
Apt 104 301 Mill Pond Ln Apartment ELECTRIC 07/12/2026
Unit 1 88 Mill Pond Ln Single family ELECTRIC WATER 06/30/2026
Unit 102, 301 Mill Pond Ln — everything held about it
Unit label Apt 102
Address 301 Mill Pond Ln, Silver Creek, TX 78611
Unit type Apartment
Size 2 bedroom · 940 sq ft
Premises Mill Pond Apartments
Vacant since 08/01/2026
Services available ELECTRIC WATER
Meters on the unit E-6114 · W-6114, both walk-by
Plan the unit carries SCW-RES · Sample — Residential · v1
Plan in force since 06/01/2026
Base charge $20.00 a month
Previous account AC-2026-00042, moved out 07/31/2026
The plan, the services and the meters belong to the UNIT — they stay when an occupant leaves, which is why they can be shown before the customer is known.
2 · WHO IS MOVING IN
Customer *
Somebody new ▼
Somebody new · A customer we already have
Search existing customers
By name, email, phone or customer number.
Full name *
Rosa Pemberton
Email
rosa.pemberton@example.com
Where the bill goes if they choose email.
Phone
+1 (512) 555-0188
Date of birth
📅
Used to tell two customers of the same name apart.
Quick action 5 of 13 · Close out · /brazosbend/accounts/a-11812 · the destructive one — two approvals and a recap before it commits
v2.234.15
SO
Sam Ortiz
Billing Clerk
Identification seen
Driver’s licence ▼
Driver’s licence · Passport · State ID · None seen
ID reference
Recorded as evidence; the number itself is not stored.
3 · WHEN SERVICE STARTS, AND THE OPENING READ
Start date
08/01/2026
Fixed to the day after the outgoing account’s move-out.
Opening read
Use the outgoing account’s final read ▼
Use the outgoing account’s final read · Enter one now · Send someone to read it
Meter E-6114 · Electric
4,180
The outgoing final read.
Meter W-6114 · Water
902
The outgoing final read.
4 · DEPOSIT
Plan
SCW-RES · Sample — Residential · v1
Taken from the unit chosen on step 1. There is no plan to pick: a plan belongs to the unit, and this account inherits it.
Deposit
Charge the scheduled amount ▼
Charge the scheduled amount · Charge a different amount · Waive it
Deposit amount
150.00
Billing cycle
Silver Creek — monthly ▼
Taken from the unit; change it only if this account bills on another round.
5 · REVIEW
What pressing the button will do
Unit Apt 102, 301 Mill Pond Ln
New customer Rosa Pemberton
Service starts 08/01/2026 · Electric and Water
Opening reads E-6114 · 4,180  •  W-6114 · 902
Plan SCW-RES v1, inherited from the unit
Deposit $150.00
A new account is opened Status: Active
Save & exit Cancel Move this occupant in
ACC-Q04
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Move-out Record payment
Adjust
Activate account
Move-in
Close out

Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
✉
🖨
$
Close this account out
Bramble Bakery · A-11812 · disconnect case DSC-26-0003 is open
✕
Close-out finishes an account whose service has already been cut.
WHEN
Service was cut
Not yet
Case DSC-26-0003 is open and a notice has been sent.
Close-out date *
📅
Cannot be earlier than the day service was cut.
WHAT IS STILL OWED
Balance
$2,410.00
An opening figure; no bill stands behind it.
Oldest unpaid item
62 days past due
What happens to the balance *
Send it to collections ▼
Send it to collections · Write it off · Keep chasing it
Deposit on file — $0.00
Nothing to settle ▼
Apply it to the balance · Refund it · Forfeit it
Write-off reason
Not applicable ▼
Uncollectable · Bankruptcy · Ceased trading · Gone away · Below the chase threshold.
Approved by
Needs a supervisor ▼
A write-off is never approved by the clerk who raised it.
LETTERS AND THE UNIT
Letters to send
Close-out letter and final statement ▼
Close-out letter and final statement · Close-out letter only · None
The unit becomes
Vacant ▼
Vacant · Handed straight to a named next occupant
Note to the file
Why this was closed out rather than moved out.
REVIEW
What pressing the button will do
Close-out date Not set — service has not been cut
Balance $2,410.00 — sent to collections
Reachability. On this deployment the button is disabled on every seeded status, and the status it exists for — disconnected — has no account at all. Bramble Bakery is the nearest thing to its case: a disconnect notice has
gone out and the cut has not happened.
Quick action 6 of 13 · Record payment · /brazosbend/accounts/a-11812 · the summary, the credits, the allocation and the remainder — on the account that proves why each one is needed
v2.234.15
SO Sam Ortiz
Billing Clerk
Payment in flight $500.00 stays in Processing
Deposit $0.00 — nothing to settle
Letters Close-out letter and final statement
The unit Becomes vacant
Account status after this Closed
Cancel
Close this account out
ACC-Q05
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Record a payment
Bramble Bakery · A-11812
✕
What this account owes today
Opening balance, carried in $2,410.00
Bills issued None — nothing has ever been billed here
Late fees None can exist — a late fee attaches to a bill’s due date, and there is no bill
Credits available to use $0.00
Already taken and not yet cleared $500.00 · Processing
Quick action 7 of 13 · Send statement · /brazosbend/accounts/a-11812 · disabled, and the form still drawn — the refusal is five words, the design is not
v2.234.15
SO Sam Ortiz
Billing Clerk
Total due now $2,410.00
THE MONEY
Amount *
500.00
Starts at the total due and can be changed.
What this money is for *
Against bills ▼
Against bills · Deposit · Plan down payment · Prepayment
Posting date *
09/11/2026 📅
The day this payment counts from.
Clearing date
09/11/2026 📅
The day the money actually arrived.
Method *
Check ▼
ACH · Card · Cash · Check · Lockbox · Money order · Wire.
Reference or cheque number
4471
Whatever the customer can quote back.
WHERE IT GOES
THERE IS NO BILL FOR THIS MONEY TO MEET
Every allocation choice on this form assumes an open bill. This account has none, so the money reduces the opening balance directly.
Apply to *
Reduce the opening balance ▼
Reduce the opening balance · Carry the whole thing as account credit.
Credit available
$0.00
Credit is spent before money is.
WHAT IT MEETS OWED THIS PAYMENT LEFT AFTER
Opening balance, 62 days past due $2,410.00 $500.00 $1,910.00
Edit the third column to change the split.
Memo
Kept with the payment and read by anyone asking why later.
REVIEW — WHAT THIS PAYMENT LEAVES BEHIND
After this payment
Total due before $2,410.00
Credit applied $0.00
Money taken now −$500.00
Still in Processing from before $500.00, not counted above
Dunning Two notices issued; a part payment does not stop the ladder
Disconnect case DSC-26-0003 Still open
Still outstanding after this $1,910.00
A part payment must say what is left, on this screen, before it commits. The form as built takes the money and shows nothing.
Cancel Record payment
ACC-Q06
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Send a statement
Bramble Bakery · A-11812
✕
WHAT PERIOD
Period *
Since the account opened ▼
The last 12 months · This year · Since the account opened · Between two dates
Covers
09/10/2024 — 09/11/2026
From
09/10/2024 📅
To
09/11/2026 📅
WHAT TO INCLUDE
✓ Bills issued
✓ Payments received
✓ Credits and adjustments
✓ The opening balance
Usage for each period
On this account only the opening balance and one payment would appear.
HOW IT GOES OUT
Send it *
By post ▼
By email · By post · Download it now
To
142 Bakers Row · Suite 1, Silver Creek, TX 78611
No email address is on file, so email is not offered.
Message to put on it
Appears above the first line.
This is the letter the customer would actually want. Two dunning notices have been sent demanding $2,410.00 and nothing has ever been issued explaining where the figure came from.
Quick action 8 of 13 · Print bill · /brazosbend/accounts/a-11812 · every field drawn over an empty selection, so the shape is settled before the first bill exists
v2.234.15
SO Sam Ortiz
Billing Clerk
REVIEW
What pressing the button will do
Period 09/10/2024 — 09/11/2026
Opening balance $2,410.00
Bills None
Payments One, $500.00, still processing
Delivery By post to the service address
Closing balance on the statement $2,410.00
Cancel
Send statement
ACC-Q07
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Print a bill
Bramble Bakery · A-11812
✕
WHICH BILL
Bill
There are no bills on this account
Onlyissuedbillscanbeprinted
What to print *
The bill exactly as it was issued ▼
Thebillexactlyasitwasissued·Rebuiltfromthestoredfigures
Quick action 9 of 13 · Issue credit · /brazosbend/accounts/a-11812 · the bill would be carried across, and the reasons are in a clerk’s words
v2.234.15
SO
Sam Ortiz
Billing Clerk
Only issued bills can be printed. The bill exactly as it was issued  Rebuilt from the stored figures
HOW IT LOOKS
Layout
Standard letter ▼
Standard letter · Large print · Two-sided
Copies
1
✓ The payment slip
✓ Messages for this cycle
The usage chart
A summary of the tariff
The usage chart cannot be included: no meter is fitted to this unit.
WHERE IT GOES
Output
Download a PDF ▼
Download a PDF · Send to a printer · Email it to the customer
Printer
Not applicable ▼
Only when sending to a printer.
REVIEW
What would be printed
Account A-11812 · Bramble Bakery
Service address 142 Bakers Row · Suite 1
Bill None selected — there are none
Stored file Not applicable
Where a bill does exist this opens the stored file — the bill as it was sent, with its name, size and checksum, rebuilt below for reading.
Cancel
Print bill
ACC-Q08
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
DEPOSIT ON FILE
$0.00
Adjust
Activate account
Move-in
Close out
Quick action 10 of 13 · Change plan · /brazosbend/accounts/a-11812 · the same three steps in one dialog, with the six internal strings the live screen shows a clerk rewritten into English
Runbooks
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
▦
▤
⚙
posting basis, from the ledger v1 · since 06/01/2026 no deposit received
⇆ ⚡📅✎
✉
🖨
$
Credit a bill
Bramble Bakery · A-11812
✕
A bill that is wrong is corrected, never edited.
WHICH BILL, AND WHAT WENT WRONG
Bill
There are no bills on this account
This account’s bills would be listed here, newest first, carried across from the screen you came
from.
What went wrong *
Choose a reason ▼
The wrong rate plan was used · The reading or the read dates were wrong · The period or the
service was wrong · A charge was missed · The customer’s name is wrong · The address is
wrong · The wrong template or language · Theft restated · Goodwill
HOW MUCH
Credit *
The whole bill ▼
The whole bill · Part of it
Amount
Cannot exceed the bill’s total.
Replacement bill
Raise it on the next run ▼
Raise it now · Raise it on the next run · Do not raise one
Case number
Optional, and searchable afterwards.
What to tell the customer
Printed on the credit note.
REVIEW
What pressing the button will do
Bill to credit None selected
Credit note —
Replacement bill —
Balance now $2,410.00
Balance once the credit posts $2,410.00
Two separate problems, and this account only has the first.
Here the icon is correctly refused: a credit corrects a bill and there is none. The $2,410.00 came in as an opening figure, so nothing in the product can reduce it — not this, and
not Adjust.
Where the icon is live it leaves the account for Billing › Fix a bill with an empty bill box, asking the clerk to paste an id they were one click from, and lists its eleven reasons as
stored values rather than sentences.
Cancel
Issue the credit
ACC-Q09
/brazosbend/accounts/a-11812

SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Change this account’s plan
Bramble Bakery · A-11812 · on SCW-RES since 06/01/2026
✕
1 The new plan 2 When & cost 3 Why & who to tell
A commercial account is on a residential plan. The plan follows the unit and the account’s category is its own fact; nothing reconciles the two, and no screen warns that
they disagree.
1 · THE NEW PLAN
Plan now
SCW-RES · Sample — Residential · v1
Read from the unit, not held on the account.
This account’s category
Commercial · small commercial
Set on the account when it was opened in September 2024.
PLAN BASE PER MONTH WHAT IT WOULD MEAN HERE
Industrial $180.00 Drops water at this unit
Residential Standard $20.00 —
Sample — Commercial $63.00 Matches the account’s category
Sample — Industrial $195.00 —
Sample — Residential $20.00 The plan now
Small Commercial $15.00 Drops electric at this unit
2 · WHEN, AND WHAT IT COSTS
When it takes effect *
On a date I choose ▼
Only a date can be used today.
New plan starts on *
10/01/2026 📅
A date inside a period already billed is refused.
Quick action 11 of 13 · Disconnect notice · /brazosbend/accounts/a-11812 · five steps, four protection questions that can each stop it, and the case that is already open
v2.234.15
SO Sam Ortiz
Billing Clerk
What it costs
Base charge on the plan now $20.00
Base charge on the new plan $63.00
Part period on the old plan, 17 days $11.33
Part period on the new plan, 13 days $27.30
Difference on the next bill $43.00
TWO THINGS THIS FIGURE LEAVES OUT
A customer moving between categories may owe a different deposit, and the rule for working that out has not been settled. Usage is priced day by day too, and pricing usage for
a period that has not happened needs a forecast nobody has chosen.
Neither gap bites here: no deposit is held and no meter has ever been read, so there is no usage to prorate.
3 · WHY, AND WHO TO TELL
Reason
Kept with the change history and read by anyone asking why later.
✓ Email the customer about this change
Record that proof of eligibility was seen
Written to the trail as evidence.
REVIEW
What pressing the button will do
From SCW-RES · Sample — Residential v1
To SCM-COM · Sample — Commercial
Starts 10/01/2026
Effect on the next bill $43.00 more
Customer told Not possible — no email on file
Cancel Change the plan
ACC-Q10
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Paymentplan Usage Meters Work Adjustments Documents Notes Audit
Adjust
Activate account
Move-in
Close out

Billing
Payments
Work
Finance
Runbooks
Reports
Settings
▤
▧
✦
▩
▦
▤
⚙
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
✉
🖨
$
Cut service at this address
Bramble Bakery · A-11812 · nothing is cut until the scheduled date
✕
1 Why 2 Protections 3 Notice & date 4 Fees 5 Review
A case is already open on this account.DSC-26-0003 was opened on 09/10/2026 and a notice has been sent, after a reminder and a ten-day notice. The form as built says
nothing, so a clerk can raise a second one.
1 · WHY
Owed
$2,410.00
62 days past due, carried in as an opening figure.
Open case
DSC-26-0003 · notice sent · opened 09/10/2026
Two dunning tiers ran before it: a reminder, then a ten-day notice.
Reason *
Non-payment — the ladder has run and they have not paid ▼
Unsafe installation · Tampering or theft · Premises abandoned · The customer asked.
What is done at the meter *
Leave connected ▼
Full disconnection · Fit a restrictor or limiter · Leave connected.
2 · PROTECTIONS — EVERY ONE MUST BE ANSWERED
Anyone on life-support equipment *
No ▼
A yes stops this outright and raises a welfare visit instead.
A medical hold on file *
No ▼
Checked against the customer record and asked again here.
A weather moratorium today
No — none in force ▼
Read from the utility’s own calendar.
Is this a landlord’s meter
No ▼
A tenant behind a landlord’s meter is notified separately.
3 · THE NOTICE AND THE DATE
How they are told *
Letter only ▼
Letter and email · Letter only · Email only · Hand delivered.
Notice goes out *
09/12/2026 📅
Service is cut on *
09/26/2026 📅
At least 14 days after the notice.
Time of day
Working hours ▼
Working hours · First thing · Any time
4 · FEES AND WHAT IT WILL COST THEM
Disconnection fee
45.00
Charged on the day service is cut.
Reconnection fee
65.00
Charged when they ask for it back.
Extra deposit to reconnect Waive any of these
Quick action 12 of 13 · Payment plan · /brazosbend/accounts/a-11812 · the schedule is worked and shown before anyone agrees to it — and it says what happens to the disconnection
v2.234.15
SO Sam Ortiz
Billing Clerk
150.00
Held before service is restored.
No ▼
No · Waive the disconnection fee · Waive all three (needs a supervisor)
These three would be the first charges ever raised on this account.
5 · REVIEW
What pressing the button will do
Existing case DSC-26-0003 — updated, not duplicated
Reason Non-payment
At the meter Leave connected — there is no meter
Protections All four answered: none in force
Notice Letter on 09/12/2026 to the service address
Service cut on 09/26/2026, working hours
Fees $45.00 now, $65.00 and a $150.00 deposit to come back
Nothing is cut before 09/26/2026
Cancel Schedule the disconnection
ACC-Q11
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Set up a payment plan
Bramble Bakery · A-11812
✕
This is the account a payment plan is for: $2,410.00 outstanding, 62 days past due, two dunning notices sent and a disconnect notice out.

WHAT IS BEING SPREAD
Arrears
$2,410.00
All of it.
Down payment
500.00
Taken today.
Down payment taken on
09/11/2026 📅
Left to spread
$1,910.00
HOW IT IS SPREAD
Number of instalments *
6 ▼
2 · 3 · 4 · 6 · 12. More than six needs a supervisor.
How often *
Monthly ▼
Weekly · Every two weeks · Monthly · On each bill’s due date
First instalment due *
10/11/2026 📅
Each instalment
$318.34
# DUE INSTALMENT RUNNING BALANCE
1 10/11/2026 $318.34 $1,591.66
2 11/11/2026 $318.34 $1,273.32
3 12/11/2026 $318.34 $954.98
4 01/11/2027 $318.34 $636.64
5 02/11/2027 $318.34 $318.30
6 03/11/2027 $318.30 $0.00
The last instalment carries the rounding.
WHAT IT DOES TO THE COLLECTIONS THAT ARE ALREADY RUNNING
The open disconnect case DSC-26-0003 *
Hold it while the plan is kept ▼
Hold it while the plan is kept · Close it · Leave it running
The dunning ladder
Pause it ▼
Pause it · Leave it running
A missed instalment restarts both, whatever is chosen here.
THE AGREEMENT
How they agreed *
On the phone ▼
On the phone · In person · By letter · Through the portal
Who agreed
The person who gave the agreement.
✓ The terms were read out and accepted
✓ They were told the disconnection is on hold, not cancelled
REVIEW
What pressing the button will do
Arrears spread $2,410.00
Down payment $500.00 today
Instalments 6 monthly, from 10/11/2026
Each $318.34, last one $318.30
Ends 03/11/2027
Disconnect case DSC-26-0003 held while the plan is kept
Dunning Paused
Quick action 13 of 13 · Add note · /brazosbend/accounts/a-11812 · a kind, a follow-up date and a recap — three things the built form does not have
v2.234.15
SO Sam Ortiz
Billing Clerk
 g
Plan total $2,410.00
Cancel Set the plan up
ACC-Q12
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$0.00
no deposit received
⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
🖨
$
Add a note
Bramble Bakery · A-11812
✕
THE NOTE
What kind *
Collections ▼
General · Collections · Dispute · Field visit · Correspondence · Complaint
Title
Disputes the opening balance
Fill in a title, a note, or both.
Note
Owner rang about the ten-day notice. Says they have never had a bill from us and will not pay $2,410 without seeing one. Checked: no bill has been issued, the
figure is an opening balance, and the unit has no meter. Holding the disconnection until this is sorted.
WHAT HAPPENS TO IT
Follow up on
09/18/2026 📅
Puts it on the collections list for that day.
Who can see it
Anyone at this utility ▼
Anyone at this utility · Billing staff only · Supervisors only
✓ Pin it to the top of the account
Letthecustomerreadit
The shortest of the thirteen, and on this account the most overdue. Two dunning notices and a disconnect case, and not one word on the record saying why.
R5 · An edit control on every group of the Overview tab NO COMMITMENT
Twelve groups, twelve controls. Asked for directly: "in the account details, in
the overview tab, give edit icon for the account service, customer plan, mailing
address, these all sections and edit option."
The rule, and it is one sentence. Every group heading on the Overview tab
carries an edit control, and a group whose contents cannot be changed carries it
disabled with the reason on it — never blank, never missing. That is BR-SHL-025
applied one level below the header, where it already governs the six action
buttons and the seven rail icons.
The product already agrees, in exactly one place. The Payment method panel
ships a → Update method control that is drawn and disabled with its reason. R5 is
that decision made general instead of made once.
Six are live, one opens a wizard, five are disabled. Plan does not get a form at
all — changing a plan is priced, dated and recorded, and a wizard for it already
exists and already works, so the control opens that rather than a second way of
doing the same thing. And two of the twelve need no new server work:
Account is a wrapper around PATCH /accounts/{id}, which is served, tested and
has no caller, and Plan is a link to a route that already runs. The other three live
controls each need one endpoint, and none of the three exists.
A drawing is not a commitment. These are descriptions until they appear in a commitment card in §12 — ACC-S15 below is that card.
R5 · The pattern, on the whole Overview tab · /brazosbend/accounts/a-11812?tab=overview · eleven groups, eleven controls — five live, one that opens a wizard, five disabled with their reason
v2.234.15
SO Sam Ortiz
Billing Clerk
Let the customer read it
The customer flag is recorded and does nothing yet: there is no customer portal in this version, so no customer can read the note either way.
REVIEW
What pressing the button will do
Kind Collections
Title Disputes the opening balance
Pinned Yes — it sits at the top of the account
Follow-up 09/18/2026, on the collections list
Customer can read it No
Written by Sam Ortiz, 09/11/2026 11:24
Cancel Save note
ACC-Q13
/brazosbend/accounts/a-11812?tab=overview
/ h i ⚑ ?
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$450.00
received 09/24/2024
MONEY ✎Edit
Balance $2,410.00
Basis Posting date
Source The ledger
Oldest unpaid 62 days
SERVICE ✎Edit
Filter ▾ ⚲  Search services
Columns ▾ ⇩  Export
SERVICE STARTED ENDED
ELECTRIC 09/10/2024 Still open
WATER 09/10/2024 Still open
PLAN — TAKEN FROM THE UNIT ✎Change plan
Plan Sample — Residential
Code SCW-RES
Version 1
In force since 06/01/2026
RECENT BILLS ✎Edit
Filter ▾ ⚲  Search bills
Columns ▾ ⇩  Export
BILL # ISSUED DUE TOTAL STATUS
BL-2608-000229 08/22/2026 09/11/2026 $811.35 Issued
BL-2607-000204 07/22/2026 08/11/2026 $812.25 Issued
BL-2606-000181 06/22/2026 07/11/2026 $786.40 Issued
ACCOUNT ✎Edit
Number A-11812
Status Active
Category Commercial
Sub-type small_commercial
Tax exempt No
Preferred language English
UNIT — WHAT THIS ACCOUNT IS ATTACHED TO ✎Change unit
Unit Suite 1
Premises 142 Bakers Row
Service address 142 Bakers Row, Silver Creek, TX 78611
Unit type Retail unit
Plan the unit carries SCW-RES v1
the address is the building’s and the plan is the unit’s — both follow this row, which is why it has
a control of its own
CUSTOMER ✎Edit
Full name Bramble Bakery
Email accounts@bramblebakery.example
Phone +1 (512) 555-0117
Business ID Seen 09/10/2024
MAILING ADDRESS — WHERE THE BILL GOES ✎Edit
Goes to Marchetti & Co, Suite 400
18 Cedar Ridge Way
Silver Creek, TX 78611
PAYMENT METHOD ✎Edit
Adjust
Activate account
Move-in
Close out
What each control does, and what it waits on
Group Control Opens What it waits on
Account Live A form in a
dialog
Nothing. PATCH /accounts/{id} is served and tested and has no caller in the front end. This is ACC-S1 / R1.
Unit Live A form in a
dialog
A PO ruling, not an endpoint. The server refuses unit by name — create-only, never patched. E07 draws it: the rule
is protecting a customer who MOVED; what has no path at all is a record that named the wrong unit.
Service Live A form in a
dialog
An endpoint. No route starts, ends or amends an account’s service agreements.
Plan Live The Change
plan wizard
Nothing — it works today. POST /accounts/{id}/plan-changes is served and wired. The control opens what already
exists rather than a second form.
Customer Live A form in a
dialog
An endpoint. GET /customers/{id} is read-only and there is no contacts route at all.
Mailing address Live A form in a
dialog
An endpoint. Note the constraint: an address lives on premises, and the mailing address is the one deliberate
exception to that.
Money Disabled — Nothing. It is worked out from the ledger; the way to change it is an adjustment.
Recent bills Disabled — Nothing. An issued bill takes no UPDATE: it is credited and replaced.
Usage trend Disabled — Nothing. It is measured; the read is what gets corrected.
Payment method Disabled — The payments module. Already shipped this way — the one panel that proves the pattern.
Deposit & credit Disabled — Nothing. It is written when a deposit payment clears.
Portal access Disabled — A customer portal. There is none in this version.
Two of the twelve need no new server work at all. Account is a wrapper
v2.234.15
SO
Sam Ortiz
Billing Clerk
USAGE TREND ✎Edit
Filter ▾ ⚲  Search periods
Columns ▾ ⇩  Export
MONTH ELECTRIC WATER
Aug 2026 5,510 kWh 62 kgal
Jul 2026 5,083 kWh 58 kgal
Jun 2026 4,870 kWh 55 kgal
May 2026 4,410 kWh 49 kgal
On file ACH · Frost Bank ••••7712
Autopay Off
DEPOSIT & CREDIT ✎Edit
Deposit on file $450.00
Received 09/24/2024
Credit tier Not computed
PORTAL ACCESS ✎Edit
Sign-in Nobody has signed up
Paperless Off
The rule. Every group heading carries the control.
ACC-E01
Two of the twelve need no new server work at all. Account is a wrapper
around a route that is already served and already tested, and Plan is a link to a
wizard that already runs. The other three live controls each need one endpoint,
and none of the three exists.
R5 · Edit the account · /brazosbend/accounts/a-11812 · the one form of the five that needs no new server work
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Adjust
Activate account
Move-in
Close out
Account
Bramble Bakery · A-11812
✕
WHAT KIND OF ACCOUNT THIS IS
Category
Commercial
Set when the account was opened and never changed afterwards: the server refuses it on this
call, because moving an account between categories reprices it.
Sub-type *
Small commercial ▼
Small commercial · Large commercial · Industrial · Municipal · Agricultural.
TAX
Tax exempt
No ▼
Yes · No
Exemption reference
The certificate number.
Exemption expires
📅
The account starts being taxed again the day after.
Preferred language
Not set ▼
The codes come from this utility’s regional settings.
DELIVERY AND CONTACT PREFERENCES
Paperless
Bills are always printed as well.
Text reminders
Autopay
Recorded on the account.
NOT EDITABLE HERE, AND EACH FOR ITS OWN REASON
Unit — an account never moves between units; a new occupant is a move-in.
Category — create-only on the server, as above.
Status—closinganaccountisthemove-outflownotanedit
The route is already there. PATCH /accounts/{id} is served, validates its payload, saves only what changed and writes an audit row, and it is covered by tests. What is missing is a wrapper in the front end, so there is no
button. Every attribute on this screen is read-only today for that reason alone.
R5 · Edit the services · /brazosbend/accounts/a-11812 · the form, and the endpoint it waits on
v2.234.15
SO
Sam Ortiz
Billing Clerk
Status — closing an account is the move-out flow, not an edit.
Returned payments and bad address — written by the returned-mail workflow, which is not built.
REVIEW
What pressing the button will change
Sub-type small_commercial →  Small commercial (display only)
Tax exempt No — unchanged
Paperless Off — unchanged
Everything else Unchanged
Written to The account, with one audit row
Cancel Save changes
ACC-E02
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Adjust
Activate account
Move-in
Close out
Services on this account
Bramble Bakery · A-11812
✕
A service agreement is this account taking one utility at this unit.
WHAT IS OPEN NOW
SERVICE STARTED ENDED
ELECTRIC 09/10/2024 Still open ✎
WATER 09/10/2024 Still open ✎
CHANGE ONE
R5 · Edit the plan · /brazosbend/accounts/a-11812 · an edit control that routes to a wizard rather than duplicating it
v2.234.15
SO
Sam Ortiz
Billing Clerk
Service *
Electric ▼
Only services this unit can take are offered.
Started
09/10/2024 📅
Moving this earlier can reprice periods already billed.
What to do *
Leave it open ▼
Leave it open · End it on a date · Correct the start date
Ends on
📅
The last day the customer is responsible for it.
ADD ONE THIS UNIT CAN TAKE
Service
Choose a service ▼
The nine this utility runs that are not already on this account.
Starts on
📅
Two services have been open here since September 2024 against a unit with no meter. Nothing has ever been measured or billed.
REVIEW
What pressing the button will change
Electric Open since 09/10/2024 — unchanged
Water Open since 09/10/2024 — unchanged
Added None
Services after this 2
Cancel
Save changes
ACC-E03
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Adjust
Activate account
Move-in
Close out
Plan
Bramble Bakery · A-11812
✕
This control does not open a form. Changing a plan is priced, dated and recorded, and a wizard for it already exists and already works.

Nothing is waiting on the server here. The preview and the commit are both served and both wired; this control is a second door to a room that is already built.
R5 · Edit the customer · /brazosbend/accounts/a-11812 · the contact a clerk actually needs to correct, and the route that does not exist
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
⚙
THE PLAN NOW
Plan
Sample — Residential
Read from the unit, not held on the account.
Code and version
SCW-RES · v1
In force since
06/01/2026
Base charge
$20.00 a month
A commercial account is on a residential plan. The plan follows the unit and the account’s category is its own fact; nothing reconciles the two and no screen warns that
they disagree.
WHAT HAPPENS WHEN YOU PRESS IT
Change plan — three steps
1 Pick the new plan, priced, with the service each one drops
2 Choose the date, and see what it costs
3 Confirm, give a reason, decide who to tell
Recorded as A plan change, with one audit row
Cancel Open Change plan →
ACC-E04
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Adjust
Activate account
Move-in
Close out
Customer
Bramble Bakery · A-11812
✕
This is one contact on one account.
WHO THEY ARE
R5 · Edit the mailing address · /brazosbend/accounts/a-11812 · the one address that is allowed to differ, and why the other one is not here
v2.234.15
SO
Sam Ortiz
Billing Clerk
Full name *
Bramble Bakery
What appears on the bill and in every list.
Kind
An organisation ▼
A person · An organisation.
Email
Where the bill goes if they choose email.
Phone
Used for text reminders and by the collections list.
Trading name
If they trade under a different name from the one on the account.
Government or business ID
Recorded as evidence that it was seen; the number itself is not stored.
LINKING
Customer record
Not linked ▼
Not linked · Link to an existing customer · Create one from this contact
Search customers
By name, email, phone or customer number.
Linking lets one customer’s accounts be seen together.
REVIEW
What pressing the button will change
Full name Bramble Bakery — unchanged
Email None — unchanged
Phone None — unchanged
Customer record Not linked — unchanged
Cancel
Save changes
ACC-E05
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Adjust
Activate account
Move-in
Close out
Mailing address
Bramble Bakery · A-11812 · where the bill goes
✕
R5 · Change the unit this account is on · /brazosbend/accounts/a-11812 · the one edit the product refuses by name — drawn, with the refusal on the button
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▦
▤
⚙
The service address is a property and belongs to the premises.
WHERE THE BILL GOES NOW
Currently
142 Bakers Row · Suite 1, Silver Creek, TX 78611
The service address, used because no separate mailing address is on file.
A MAILING ADDRESS OF ITS OWN
Send the bill to *
The service address ▼
The service address · A different address
Addressee
If the bill should be addressed to somebody other than the account name.
Street
Second line
Suite, floor, care-of.
Town or city
State ZIP
Send notices here too
Dunning notices and disconnect notices, not only the bill.
NOT EDITABLE HERE
The service address is not on this form. It is the property’s, not the account’s, and every screen that shows one walks to the premises to get it.
REVIEW
What pressing the button will change
Bill goes to The service address — unchanged
Notices go to The service address — unchanged
Cancel
Save changes
ACC-E06
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
Move-out Record payment
Adjust
Activate account
Move-in
Close out
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Unit
Bramble Bakery · A-11812 · currently Suite 1, 142 Bakers Row
✕
This corrects a record. It does not move a customer.
If the customer has actually moved, close this and use Move-out, then Move-in at the new unit — two accounts, because the bills, the meters and the readings belong to the
unit and must not follow a person.
1 · FIND THE UNIT IT SHOULD BE ON
Search for a unit *
142 bakers row
Type an address, a unit label or a premises name.
UNIT PREMISES TYPE OCCUPANT VACANT SINCE
Suite 1 142 Bakers Row Retail unit This account —
Suite 2 142 Bakers Row Retail unit Vacant 03/14/2026
Suite 3 142 Bakers Row Retail unit Kestrel Print Co · A-11907 —
Suite 3 is listed and refused rather than hidden, so a clerk can see the unit exists and who has it.
2 · EVERY ASPECT OF BOTH UNITS, SIDE BY SIDE
Suite 1 — now
Unit number U-000417
Label Suite 1
Unit type Retail unit
Floor Ground
Floor area 1,840 sq ft
Premises 142 Bakers Row · PR-0188
Service address 142 Bakers Row, Silver Creek, TX 78611
Map point Reads the building’s
Parcel —
Plan SCW-RES · Sample — Residential · v1
Plan in force since 06/01/2026
Plan locked No
Bill the owner when vacant No
Meters E-4417 · W-4417
Services available ELECTRIC WATER
Suite 2 — chosen
Unit number U-000418
Label Suite 2
Unit type Retail unit
Floor First
Floor area 2,260 sq ft
Premises 142 Bakers Row · PR-0188
Service address 142 Bakers Row, Silver Creek, TX 78611
Map point Its own — rear entrance
Parcel TR-4417-02
Plan SCW-COM · Sample — Commercial · v2
Plan in force since 01/01/2026
Plan locked Yes
Bill the owner when vacant Yes
Meters E-4418 · W-4418
Services available ELECTRIC WATER
Every value that would change is marked.
3 · WHAT THIS DOES TO THE ACCOUNT
This collides with a signed rule and needs a ruling rather than a build. services.update_account refuses unit by name — create-only, never patched — citing BR-CUS-017. That rule is protecting the right thing: a
customer who has moved must leave by move-out and arrive by move-in, because the bills, meters and reads belong to the unit and must not follow a person. But it also blocks a different case the product has no path for
at all: a record that named the wrong unit. Nobody moved; the account has simply been billing against the wrong meters. Today the only way out is to close the account and open another, which loses its history to fix a
typo What is being asked of the PO is narrow: may an account be re-pointed at another unit as a CORRECTION with a reason a supervisor and issued bills left alone? Everything else about BR-CUS-017 stands
v2.234.15
SO Sam Ortiz
Billing Clerk
What changes
Service address Unchanged — it is the building’s, not the unit’s
Plan SCW-RES v1 →  SCM-COM v2, and it is LOCKED on the new unit
Base charge $20.00 →  $63.00 a month
Meters E-4417/W-4417 →  E-4418/W-4418
Reading history Stays with Suite 1 — it does not follow
Billing cycle Unchanged — both units are on Silver Creek monthly
Route Changes — the new meters sit on a different walk
Effect on the next bill $43.00 more a month
Two of those deserve saying out loud.
The address does not move. An address belongs to the building, and both suites are in it.
4 · WHAT IS ALREADY BILLED, AND CANNOT BE UNDONE
FIVE BILLS HAVE BEEN ISSUED AGAINST SUITE 1
An issued bill is a permanent record and is never reissued, so those five keep the unit and the charges they were sent with. Correcting the account from today does not correct
them — a bill that was wrong is credited and replaced, which is its own flow.
5 · WHY, AND WHO SAYS SO
Reason *
The account was opened on the wrong unit ▼
The account was opened on the wrong unit · The units were relabelled · An import put it in the
wrong place
Approved by
Needs a supervisor ▼
Nobody moves an account between units on their own signature.
Note to the file
What went wrong, and how it was found.
Tell the customer the suite on their bill has changed
The address is the same, so the envelope is unchanged; the suite line on the bill is not.
6 · REVIEW
What pressing the button would do
Account A-11812 · Bramble Bakery
From Suite 1 · U-000417
To Suite 2 · U-000418
Effective Today — a correction is not backdated
Plan Changes with the unit, and locks
Five issued bills Untouched
Reason The account was opened on the wrong unit
Approval Waiting on a supervisor
Cancel
Change the unit
ACC-E07
typo. What is being asked of the PO is narrow: may an account be re-pointed at another unit as a CORRECTION, with a reason, a supervisor and issued bills left alone? Everything else about BR-CUS-017 stands.
R6 · A Communication action on the account NO COMMITMENT
An eighth icon on the quick-action rail, and the dialog behind it in two
views. Asked for directly: "add a communication action to the quick action
sections. here the user can send quick communication to the customer."
Two views, because a collections call has two halves. Write a message
composes one. What has already gone out answers the question a customer
actually asks first — and on this account the answer is three notices in one
fortnight, one of which failed.
Three product rules shaped this form rather than decorating it
Nothing is ever sent from a screen. BR-NOT-005: the output of every notice path is queue rows, and there is no SMTP, ESP, Twilio or print-vendor call anywhere in the module. So
the commit reads Queue the message, not Send, and the dialog says where it goes next. A wireframe with a Send button would promise an architecture this product has
deliberately refused.
Free text does not exist on a regulated step. BR-PAY-035 fixes the tone to the tier — friendly is the due+3 reminder, firm is the ten-day, final is the 5-day/48h — and BR-NOT-008
renders the disconnect class whatever tone was picked. So the message box is live for a courtesy note and refused, with its reason, the moment a ladder step is chosen. What a
customer was told has to be provable later.
A text message supplements a letter and never replaces it (A19 rule 3). On a regulated kind the postal channel is ticked and cannot be unticked.
None of those ids appears on the dialog itself. B14 rule 32 keeps them out of clerk-facing copy, and unlike the Change plan quote there is no product behaviour here to reproduce
faithfully — this is a proposal, so it is written the way it should ship.
What already exists and what does not. The outbound queue, its search and
filters, its failed and bounced first sort, and Resend and Requeue are all served
today. What does not exist is composing a message from an account: there is no
ad-hoc send path anywhere in the module, which is the one thing ACC-S16 is
asking for.
One question this raises and does not answer. Send statement is already a rail
icon and is also a communication. If R6 is built, that icon is arguably one kind
inside this dialog rather than a control of its own. Left as it is here, because
collapsing a control a clerk already knows is a decision for the PO and not for a
drawing.
A drawing is not a commitment. These are descriptions until they appear in a commitment card in §12 — ACC-S16 below is that card.
R6 · Write a message · /brazosbend/accounts/a-11812 · the compose view — free text, because this one is a courtesy message
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
←  Accounts
ACCOUNTA 11812 CUSTOMER NOTLINKED

Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$450.00
received 09/24/2024
💬 🖨 $ ⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
Communication
Bramble Bakery · A-11812
✕
Write a message What has already gone out
WHAT TO SEND
Kind of message *
A courtesy message ▼
A courtesy message · A payment reminder · A notice about the disconnection · A copy of a bill ·
Proof of the balance
Template
Free message — you write it ▼
Free message · Balance summary · Payment options · We have not heard from you.
WHO IT GOES TO
Customer
Bramble Bakery · one contact, no customer record linked
Language
English
From the account.
CHANNEL GOES TO ON FILE?
✓ Email accounts@bramblebakery.example Yes
Text message +1 (512) 555-0117 Yes
Post 142 Bakers Row · Suite 1, Silver Creek, TX 78611 Yes
A channel with nothing on file is shown and cannot be ticked, so a clerk can see what is missing rather than wonder why an option vanished.
THE MESSAGE
Subject
About your account balance
Shown on email only.
Sign it as
Brazos Bend Utilities ▼
Brazos Bend Utilities · Sam Ortiz, Billing · The billing team
Message
Hello, following our call today: the $2,410.00 on your account is an opening balance carried over, and no bill has been issued for it. I am looking into where it came
from and will call you back by Friday. The disconnection is on hold until then.
Live for a courtesy message.
Att hth b l t t t
Three product rules shaped this form rather than decorating it. BR-NOT-005: output is queue rows and nothing is ever sent inline, so the commit queues. BR-PAY-035 and BR-NOT-008: the tone of a ladder step IS the tier
and free-text tones do not exist, so the message box is refused the moment a reminder or a notice is chosen. A19 rule 3: a text message supplements a mailed notice and never replaces it, so on a regulated kind the postal
channel is ticked and cannot be unticked. None of the three ids appears on the dialog — B14 rule 32 keeps them out of clerk copy.
R6 · What has already gone out · /brazosbend/accounts/a-11812 · the history view — what was sent, on which channel, and what came back
v2.234.15
SO Sam Ortiz
Billing Clerk
Attach the balance as a statement
Attaches what the statement screen would produce.
WHEN
Queue it *
Now ▼
Now · On a date I choose
On
📅
Nothing leaves before this date.
REVIEW
What pressing the button will do
Kind A courtesy message, written by you
Goes to accounts@bramblebakery.example
Channels Email only
Signed Brazos Bend Utilities
Queued Now
It is queued, not sent The outbound queue delivers it
This screen does not send anything. It writes a row on the outbound queue, and the queue delivers it.
Save as a draft Cancel Queue the message
ACC-C01
/brazosbend/accounts/a-11812
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Accounts / A-11812 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
←  Accounts
ACCOUNT A-11812  ·  CUSTOMER — NOT LINKED
Bramble Bakery
Active Billable Commercial · Small commercial Regular account
Autopay off
⌂ 142 Bakers Row · Suite 1  ·  Silver Creek, TX 78611  ·  Since Sep 2024
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
BALANCE
$2,410.00
posting basis, from the ledger
DUE DATE
Not known yet
past-due is not worked out here
PLAN FROM UNIT
SCW-RES
v1 · since 06/01/2026
DEPOSIT ON FILE
$450.00
received 09/24/2024
💬 🖨 $ ⇆ ⚡📅✎
Adjust
Activate account
Move-in
Close out
✉
Drawn from what the outbound queue really serves: search on recipient, account and reference, filters on type, channel, status and date range, and the ratified default sort — failed and bounced first, then queued, so the
handful of failures are not buried under rows that are fine. Resend and Requeue are real endpoints; composing a new message from an account is the part that does not exist.
R7 · A master account lists the accounts at its address NO COMMITMENT
A thirteenth tab, shown only when the account’s kind is master, sitting
immediately after Overview. Ruled: "change the premises tab to accounts tab.
And in that, show only one table with all the accounts that are associated with this
master account and with their account status."
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
⚙
Communication
Bramble Bakery · A-11812
✕
Write a message What has already gone out
The first thing a customer asks on a collections call is what they have already been sent.
Filter ▾ ⚲  Search by subject, template or reference Filter ▾ Columns ▾ ⇩  Export
SENT ▼ WHAT CHANNEL GOES TO STATUS
09/10/2026 Disconnect notice — ten
day
Certified post +
Email
Suite 1 · accounts@… Delivered 09/12 ☰Open
09/10/2026 Payment reminder — firm Post + Email Suite 1 · accounts@… Delivered 09/12 ☰Open
08/27/2026 Payment reminder —
friendly
Text message +1 (512) 555-0117 Failed — number not
reachable
↻Resend
08/27/2026 Payment reminder —
friendly
Email accounts@bramblebakery.example Delivered ☰Open
12/08/2025 Payment plan agreement Email accounts@bramblebakery.example Delivered ☰Open
1–5 of 5  ·  failed and bounced first, then newest  ·  Rows per page 50 100    ‹ ›
The failed text message is the row that matters, which is why the list puts failures first. The friendly reminder reached them by email and not by text, and nothing on
the account screen says so today — a clerk telling a customer “we texted you” would be wrong.
WHAT A SENT MESSAGE DOES NOT TELL YOU
DELIVERED IS THE CARRIER’S WORD, NOT THE CUSTOMER’S
A delivered email reached a mailbox. Whether anybody opened it is not recorded, and this screen will not imply that it was.
A POSTED LETTER HAS NO DELIVERY DATE
Post is queued and handed to a print vendor; there is no confirmation to show except on certified mail, which has its own register.
Every row here is a row on the outbound queue.
Write a message Close
ACC-C02
“Associated” is by ADDRESS, and the tab says so rather than letting a list imply otherwise
BR-CUS-068: a master account is an ordinary account row with its kind set to master. The payer is the premises’ owner or manager, and it is attached to the premises’ common-
area units. There is no parent_account_id, no child accounts and no rolled-up balance. So the accounts on this tab are the accounts at the same address — which is what a clerk
ringing about a building actually needs — and the drawing states plainly that a tenant’s account is its own and so is its money.
There is deliberately no total under the balance column. The six accounts sum to $810.95 and that figure means nothing: two of the rows are $0.00 and one of them is this
account, so what it really adds up to is the owner’s own $69.60 plus $741.35 owed by three different tenants who have nothing to do with each other. Printing it where an owner
can see it invites exactly the wrong conclusion, and the drawing says why it is absent rather than leaving a gap somebody helpfully fills in.
The master is in the list, marked as the one you are on. It is an ordinary
account row, so leaving it out would be the odd choice — and its unit column
reads common areas ×2, because one master covers several by hanging off the
ADDRESS and reaching every one of them through its own service agreements.
That read exists because billing once priced the anchor unit and nothing else:
right for an ordinary account, and two-thirds right for a master (DEF-571,
whose worked case is this very address — 1408 Elm, $41.20 + $28.40 = $69.60).
What those units add up to belongs on the account’s Bills tab, not here.
Status is on every row, across the five the rest of this document tests against,
and the toolbar filters on it — which is the point of the tab: one of these six is in
collections and one is on a vacation hold, and neither is visible from anywhere
else in the building.
Nothing here needs a new table and none of it needs a new relationship. It
is an account list with a premises filter and a status column. What is missing is
the tab.
A drawing is not a commitment. These are descriptions until they appear in a commitment card in §12 — ACC-S17 below is that card.
R7 · The Accounts tab, on a master account · /brazosbend/accounts/a-10001?tab=accounts · shown only when the account’s kind is master, immediately after Overview
/brazosbend/accounts/a-10001?tab=accounts
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Accounts / A-10001 ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
←  Accounts
ACCOUNT A-10001  ·  OWNER OF 1408 ELM STREET
Elm Street Holdings
LLC
Active Billable Master account Residential · Multi-family
Autopay off
⌂ 1408 Elm Street  ·  Silver Creek, TX 78611  ·  Since Mar 2023
ELECTRIC WATER
 + 9 more ▾
Move-out Record payment
Overview Accounts Bills Payments Credits Payment plan Usage Meters Work Adjustments Documents Notes Audit
Adjust
Activate account
Move-in
Close out
What the tab links, and what it deliberately does not
On the tab How it is linked Where it comes from
Every account at the
address, the master
among them
By address only. No parent, no children, no
rolled-up balance and no total under the
balance column
A filtered account list, scoped to the premises. A tenant account is its own account and so is its
money.
Status, on every row Each account’s own The same five statuses the rest of this document tests against — active, marked disconnect,
vacation hold, pending activation, closed.
The master’s unit
column, reading
common areas ×2
A real, direct linkage — this account’s own open
service agreements
covered_unit_ids(account). It answered anchor + the agreement units until 2026-09-01 and answers
the agreement units now — same units, same $69.60. What those units add up to belongs on Bills,
not here.
The tab itself Shown only when kind = master An ordinary account row with one column set. The only door to it is the create-a-master path;
every other account route refuses the field by name.
Finance
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▩
▦
▤
⚙
BALANCE
$69.60
this account’s own — the owner bill
ACCOUNTS HERE
6
every account at 1408 Elm Street
ACTIVE
3
billing normally
NEEDING ATTENTION
2
one in collections, one on hold
UNITS WITH NO ACCOUNT
1
vacant, and nobody is billed for it
💬 🖨 $ ⇆ ⚡📅✎
Sample data. The rows are invented to show the layout working; what the product can and cannot link is not.
All Active Needing attention Closed Filter ▾ ⚲  Search by account, occupant or unit Columns ▾ ⇩  Export
ACCOUNT UNIT OCCUPANT KIND STATUS SINCE BALANCE
A-10001 Common areas ×2 Elm Street Holdings LLC Master Active 03/06/2023 $69.60 This account
A-11602 Unit E Ncube, T. Regular Marked disconnect 07/19/2024 $512.80 ↗Open
A-11455 Unit B Tan, Wei Regular Active 02/14/2025 $186.40 ↗Open
A-11890 Unit D Fairbanks, J. Regular Vacation hold 05/02/2024 $42.15 ↗Open
A-12007 Unit C Reyes, M. Regular Pending activation 04/28/2026 $0.00 ↗Open
A-10432 Unit A Okafor, D. Regular Closed 06/02/2023 $0.00 ↗Open
1–6 of 6  ·  Rows per page 50 100 200    ‹ ›
These are related by ADDRESS, not by a link. A master account has no parent and no children: a tenant’s account is its own, and so is its money.
The master is in the list, marked as the one you are on. It is an ordinary account row with its kind set to master, so leaving it out would be the odd choice — and its unit column reads common areas ×2 because one
master covers several: it hangs off the address and reaches every one of them through its own service agreements.
UNIT F HAS NO ACCOUNT AT ALL
It is vacant and its vacant-standby flag is off, so nobody is billed for it — not a tenant, because there is none, and not the owner. A vacant unit bills the owner ONLY where that unit’s own flag is set, which is what
separates a common area from an empty one.
A MASTER ACCOUNT HAS NO CHILD ACCOUNTS
Nothing points at it and nothing is owned by it, so there is no tree to draw and no rolled-up balance to show. What makes it a master is the units its own agreements reach.
✉
ACC-M01 · sample data
Nothing here needs a new table and none of it needs a new relationship. It
is an account list with a premises filter and a status column. What is missing is
the tab.
One thing left off on purpose: there is no total under the balance column. The
six rows sum to $810.95 and that number means nothing — it is the owner’s
own $69.60 plus $741.35 owed by three different tenants who have nothing to
do with each other. Printing it where an owner can see it invites exactly the
wrong conclusion, so the column has no foot.
R8 · A company customer and the master account it belongs under ACC-S18
Ruled, and it withdraws the chooser drawn in version 41: "Don’t add any
account selection there. Just keep the customer kind only. If the user selects
company, then ask user to select the associated company master account. where
user can search and select it."
The first half is simple and is done. The wizard asks no account-kind question
at all — the three-way chooser, the master branch and the second-master
refusal are withdrawn. Customer kind is the only branch on the step, and every
account this screen opens is a regular account, which the server already
enforces.
⚠  The second half collides with a ruling of yours, and the collision is worth more than the field
There IS a parent-child link between accounts, it is called a sub-account, and you ruled it. BR-CUS-171, 2026-08-27, closing OQ-531: an occupying account is a child of the
premises’ owner account. A master answers its children and every other account answers its master. It is live in the product today, under that name, on the account read and on the
move-out screen. This document told you last version that there was no such thing. That was wrong, and this section is the correction.
The link is DERIVED and stored nowhere — which is why no column exists, and it is a design rather than a gap. It needs no maintenance: "occupying" keys off the status’s
behaviour class and never its label, so a closed tenant drops out of the list on the day they close and a pending one never appears. Nobody has to remember to unlink anything.
⚠  And the way the owner is found was superseded the same day, for the exact reason a free picker reopens. It used to be worked out geometrically — walk the common
areas, treat whoever pays for the hallway as the owner. You replaced all of it (DEF-650, decision 4), verbatim: "the premises names its owner, the owner is the master, and nothing is
inferred from hallways." The old reading was retired rather than kept as a fallback, and the reason given was that "a fallback that disagrees with the declared owner would silently
bill a different party."
BR-CUS-097 says it again from the money side: a transfer cannot be built against an ambiguous target, so the move-out screen takes its master resolved from the server and has
no free-text account field at all — a forged transfer is unrepresentable rather than merely rejected.
So the association you want the clerk to pick is already answered, and the thing that answers it is the service address — step 2 of this very wizard.
So both are drawn: the picker as asked, and the check that keeps it from reversing your own ruling by accident
ACC-K01 to ACC-K03 are the field exactly as you described it — under Company, search and select, with the three states a clerk actually meets. ACC-K04 and ACC-K05 are the review
step, where both answers are in hand for the first time.
A pick that AGREES with the address costs nothing and reads as a confirmation (ACC-K04). A pick that DISAGREES is the silently-bill-a-different-party case (ACC-K05): the
address names one owner, the picked account belongs to another, and the screen cannot tell which is wrong. It is stopped rather than saved with a warning, because the
, p g , g pp g,
consequence surfaces months later as a debt pointed at a company that never had anything to do with the tenant. Three ways out are offered and one of them is not on this screen
at all — if the building’s declared owner is wrong, that is fixed on the premises, which is precisely what your ruling says.
The check needs nothing new. Both answers are already available by the review step: the clerk’s pick, and master_account_for, which has been on the account read since the day
the rule was built.
The search half needs nothing built. The storing half needs a decision first.
Searching master accounts is already served. The account list takes f.kind=master — a filter added so a screen could "list the owner accounts without a second endpoint" — and
its search already covers account number, customer number, company name, service address and meter. ACC-K02 is a screen over a query that exists.
Storing a hand-picked master is the part with a cost, and it is not the column. Adding a field is easy; deciding which of the two answers wins when they differ is the real
question, and the retired mechanism was retired for exactly that reason. The cheaper answer may be that the clerk never picks at all — the address already decides it, and the
field becomes a shown, derived fact with the picker reserved for correcting it. That is a ruling, and it is yours; the drawing shows what you asked for rather than quietly substituting
it.
It records a relationship. It moves money in exactly one place.
ACC-K04 says on screen what the association does not do: nothing is rolled up and no balance is combined. The shop’s own supply is billed here, the hallway lighting and irrigation
are billed there, and they stay two bills for two different things.
The one place a master association ever moves money is a move-out, where a departing tenant’s unpaid residue can be tied back to the landlord — and your own ruling made
that a clerk’s deliberate act rather than a consequence: "if U1 leave and dont pay $500 then $500 Debt is shifted to Owner A, if clark tied back to A during move out process". Nothing
is preselected there, and the consequence — that the reminder ladder then points at the landlord — is shown before the click, not after.
A drawing is not a commitment. These are descriptions until they appear in a commitment card in §12 — ACC-S18 below is that card.
Step 1 · company picked, and the master account it belongs under · /brazosbend/accounts/new?step=1 · ACC-K01 · proposed · customer kind is the only branch
/brazosbend/accounts/new?step=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
←  Accounts
NEW ACCOUNT  ·  STEP 1 OF 5
Customer
1 Customer 2 Service address 3 Account preferences 4 Deposit 5 Review
Customer
Category *
Commercial ▼
Full name *
Elm Street Holdings LLC
Email
accounts@elmstreetholdings.example
Phone
(512) 555 ‑ 0330
Customer kind *
Acompany ▼
The picker, open · search and select over the company’s master accounts · /brazosbend/accounts/new?step=1 · ACC-K02 · proposed · three results, and an explicit none
Runbooks
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
▦
▤
⚙
A company ▼
A person · A company.
Nothing appears under Person. Customer kind is the only branch on this step, and the step asks no other kind of question — there is no master-or-regular choice anywhere in this wizard, and every account it opens is a
regular account.
Company
Associated master account
A ‑ 10001 · Elm Street Holdings LLC · 1408 Elm Street ▼
Search by account number, company name or address.
⚲  Search master accounts Change Clear
The account you picked
Account A ‑ 10001
Owner Elm Street Holdings LLC
Address 1408 Elm Street · Silver Creek, TX 78611
Status Active · since 03/06/2023
Covers Two common areas — hallway lighting, irrigation
A company can have more than one, which is why this is a search and not a lookup. A master account belongs to an ADDRESS — one per building — so a company that owns three buildings has three of them.
THE PRODUCT ALREADY WORKS THIS OUT, AND NOT FROM HERE
An account’s master is DERIVED from its service address: the premises names its owner, and the owner is the master. That address is step 2 of this wizard, so at step 1 there is nothing yet to derive it from - which is why
this field can only be searched here, and why the review step checks the two against each other.
IDENTITY — STORED ENCRYPTED
Company number *
TX ‑ 4471 ‑ 08
Tax id
••••••3390
Continue
Back
ACC-K01
/brazosbend/accounts/new?step=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
←  Accounts
NEW ACCOUNT  ·  STEP 1 OF 5
Customer
1 Customer 2 Service address 3 Account preferences 4 Deposit 5 Review
Customer
Category *
Commercial ▼
Full name *
Elm Street Holdings LLC
Email
accounts@elmstreetholdings.example
Phone
(512) 555 ‑ 0330
Customer kind *
A company ▼
The company has no master account · a real state, and not a dead end · /brazosbend/accounts/new?step=1 · ACC-K03 · proposed · empty, not zero-results
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▦
▤
⚙
A person · A company.
Select the associated master account
Elm Street Holdings LLC · three master accounts
✕
SEARCH
⚲  elm street ✕
Account number, company name or address.
This company All companies Active Filter ▾ ⚲  Search this list
Columns ▾ ⇩  Export
ACCOUNT COMPANY ADDRESS STATUS COVERS SINCE
A ‑ 10001 Elm Street Holdings LLC 1408 Elm Street Active 2 common areas 03/06/2023
A ‑ 10044 Elm Street Holdings LLC 77 Cedar Court Active 2 common areas 11/20/2024
A ‑ 10071 Elm Street Holdings LLC 310 Marigold Way Pending activation 1 common area 08/02/2026
1–3 of 3  ·  Rows per page 50 100 200    ‹ ›
Not associated with a master account
A company that rents its premises has none.
This list is already served. The account list takes a filter that narrows it to master accounts, and its search covers account number, company name and service address.
Cancel Select A ‑ 10001
ACC-K02
/brazosbend/accounts/new?step=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
←  Accounts
NEW ACCOUNT  ·  STEP 1 OF 5
Customer
1 Customer 2 Service address 3 Account preferences 4 Deposit 5 Review
Customer
Category *
Commercial ▼
Full name *
Bramble Bakery LLC
Email
hello@bramblebakery.example
Phone
(512) 555 ‑ 0114
Customer kind *
A
Step 5 · the pick agrees with the address, so it is a confirmation · /brazosbend/accounts/new?step=5 · ACC-K04 · proposed · and what it does not do
Runbooks
Reports
Settings
v2.234.15
SO Sam Ortiz
Billing Clerk
▦
▤
⚙
A company ▼
A person · A company.
Select the associated master account
Bramble Bakery LLC · no master accounts
✕
SEARCH
⚲  bramble ✕
This company All companies Active Filter ▾ Columns ▾
BRAMBLE BAKERY LLC HAS NO MASTER ACCOUNT
A master account belongs to whoever OWNS a building. This company rents its premises, so there is no master account for it to belong under - and there is nothing here for the
clerk to fix.
Not associated with a master account
Pre-selected, because it is the only true answer for this company.
Empty is not the same as no matches. This company has none at all, which is an ordinary state and reads differently from a search that matched nothing — that one keeps the
search box and offers to clear it.
Cancel Continue without one
ACC-K03
/brazosbend/accounts/new?step=5
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
NEW ACCOUNT  ·  STEP 5 OF 5
Review
1 Customer 2 Service address 3 Account preferences 4 Deposit 5 Review
Customer
Name Elm Street Holdings LLC
Customer kind Company
Company number TX ‑ 4471 ‑ 08
Account
Category Commercial · Small commercial
Service address 1408 Elm Street · Unit G · Silver Creek, TX 78611
Plan Commercial Standard — from the unit
Opens 09/15/2026
Master account
You picked A ‑ 10001 · 1408 Elm Street
Thisaddress’sowner ElmStreetHoldingsLLC
Step 5 · the pick disagrees with the address — the case the picker adds · /brazosbend/accounts/new?step=5 · ACC-K05 · proposed · two owners, and the screen cannot choose
v2.234.15
SO Sam Ortiz
Billing Clerk
This addresss owner Elm Street Holdings LLC
Their account A ‑ 10001 · the same one
✓  The two agree, so there is nothing to decide. The product works an account’s master out on its own: the premises names its owner, and the owner’s account is the master.
What the association does, and what it does not. It records that this account is a sub-account of the company’s account for the building.
Deposit
Deposit
Required by the plan $400.00
Taken now · cheque 4471 $400.00
Still to collect $0.00
Save as
Activate
Billable from today.
Draft
Kept, not billed, activated later.
Back Create account
ACC-K04
/brazosbend/accounts/new?step=5
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
NEW ACCOUNT  ·  STEP 5 OF 5
Review
1 Customer 2 Service address 3 Account preferences 4 Deposit 5 Review
Account
Customer Elm Street Holdings LLC · Company
Service address 220 Willow Bend · Unit 4 · Silver Creek, TX 78611
Opens 09/15/2026
Master account
You picked A ‑ 10001 · 1408 Elm Street
This address’s owner Willow Bend Partners LP
Their account A ‑ 10210 · 220 Willow Bend
These name two different owners. 220 Willow Bend is owned by Willow Bend Partners LP, and the account picked at step 1 belongs to Elm Street Holdings LLC at another address. One of the two is wrong and the
screen cannot tell which.
Why this is stopped rather than saved with a warning. A master is how an unpaid residue finds a landlord at move-out.
The three ways out
IF… THEN WHERE
The address is right Use A ‑ 10210, this building’s own owner account ↗Use this one
Themasterisright Gobackandcorrecttheserviceaddress ↗Step 2
The piece Where it stands today What it costs
Customer kind —
person or company
Built, and unchanged by any of this. It is the only branch on the step. Nothing.
Searching master
accounts
Already served. The account list takes f.kind=master — added so a screen could list
owner accounts without a second endpoint — and its search covers account number,
customer number, company name, service address and meter.
The picker screen. No endpoint, no query, no index.
The account’s master Already answered, and already on the account read. master_account_for(account)
resolves premises → declared owner → that owner’s account (BR-CUS-171, BR-MET-400),
and sub_accounts_for_master runs it the other way.
Nothing — it is the thing the picker would be duplicating.
Storing a hand-
picked master
No column, on purpose. The link is DERIVED and stored nowhere, so it needs no
maintenance: a closed tenant drops out on the day they close and a pending one never
appears.
A ruling before a column. Storing a second answer means
deciding which of the two wins when they differ — and
the retired mechanism was retired for exactly that
reason.
A company with
several
Expected. A master belongs to an ADDRESS, one per building (BR-CUS-1011), so a
company owning three buildings has three.
Why it is a search. Nothing extra.
A company with none Ordinary. A company that rents owns no building and so has no master account. An explicit not associated answer, so the field can be
asked of every company without blocking the ones it
cannot apply to.
The pick disagreeing
with the address
The case the picker ADDS, and the only one with a cost. The move-out tie-back
resolves its target from the server precisely so a transfer cannot be built against
an ambiguous one (BR-CUS-097).
The check in ACC-K05, which needs nothing new — both
answers are already in hand by the review step.
R9 · The customer you already have, flagged where the details are typed ACC-S19
Ruled: "the system should flag if the details were already attached to any of the
accounts in the system and should show the details of the customer account with
the proper customer details. This is very important scenario."
⚠  Most of this is built, and what is missing is the screen — which changes
what the remedy costs from a matcher to a panel. The criteria were ruled on
2026-08-25, verbatim "Name + date of birth + one government ID", the strictest
of the three readings offered: the Product Owner took refusing some genuine
returners over the risk of handing a stranger somebody else’s deposit. The
evidence exists — a date of birth, a Social Security number, a driving licence and
a phone, each identifier encrypted with a one-way token beside it, so a match is
computed without anybody reading the number. And one function resolves
the party for four doors and answers in a single word: linked, created or
v2.234.15
SO
Sam Ortiz
Billing Clerk
The master is right Go back and correct the service address ↗Step 2
Willow Bend’s owner is wrong The building names its owner — fix it on the premises, not here ↗Premises
Back
Create account
ACC-K05
none.
That word reaches no screen. The door’s own note says why it matters: "The
server has always known whether it linked or created; it recorded the fact in the
audit row and dropped it from the response, so no screen could tell a clerk which
of the three things had happened." The cost is already on the register: one
landlord holding three customer numbers.
The three doors do not behave the same, and the drawings say which is which. The new account and the move-in both resolve a customer through the same function — the
move-in requiring an identifier outright, on the ruling "You either create new Customer ID or you link existing customer ID here". The service request creates nothing at all,
deliberately and by a pinned rule, so its flag can only ever be advice. Drawing one panel across all three would have been the easiest possible mistake.
/brazosbend/accounts/new?step=2
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
NEW ACCOUNT
Who the customer is
Step 2 of 5 · The customer
Save & exit
✓ The unit 2 The customer 3 Account preferences 4 Deposit 5 Review
The customer
Customer kind
A person ▼
Full name *
Okonkwo, Adaeze
Date of birth *
03/14/1991 📅
Email
a.okonkwo@example.com
Identity — one of these is enough to open an account
Social Security number
•••-••-2208
Driving licence
Not given
Phone
(512) 555 ‑ 0164
This looks like somebody you already have
CUSTOMER NUMBER ACCOUNTS MATCH
Okonkwo, Adaeze · born 03/14/1991 C-00412 2 · 1 open Strong
Name Agrees
Date of birth Agrees · 03/14/1991
Social Security number Agrees
Phone Different — (512) 555 ‑ 0910 on file
Email Different
What linking them would carry over
Held under C-00412 today
Deposit on the closed account $150.00
Deposit interest — not recorded
Payment history 4 years, no arrears
Deposit you would take today $0.00
This is why the flag is a money feature and not a convenience. Left
unlinked, this customer is a stranger: they are asked for a fresh $150.00 while
the utility is already holding theirs, and four clean years of history counts for
nothing against their deposit band.
What you choose
Link to C-00412
One customer, two accounts.
Create a new customer anyway
Needs a reason, recorded against your name.
Go back and check the details
Nothing is preselected, on purpose. The check is advice and the clerk decides.
What the server already answers
Outcome linked · created · none
R9 · the new account wizard, matching as you type · /brazosbend/accounts/new?step=2 · Name, date of birth and one government ID — the criteria the PO chose
v2.234.15
SO
Sam Ortiz
Billing Clerk
Three things agree and two do not, and both halves are shown. A person moves and changes their number; that is not
evidence they are somebody else.
Open C-00412 and see what they hold →
A reuse reads linked, with reused beside it
Where it is recorded The audit row, every time
Where it is shown Nowhere, today
The matching is built; the panel above is not. Four doors already resolve
a customer this way and every one of them knows in a single word whether it
linked or created — and drops it before any screen sees it.
←  Back Continue →
ACC-S19
/brazosbend/accounts/new?step=2&match=c-00412
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Accounts / New account ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Accounts
NEW ACCOUNT
Who the customer is
Step 2 of 5 · The customer
Save & exit
✓ The unit 2 The customer 3 Account preferences 4 Deposit 5 Review
Okonkwo, Adaeze · C-00412
What this customer already holds
✕
THE CUSTOMER ON FILE
Customer number C-00412
Name Okonkwo, Adaeze
Kind Person
Date of birth 03/14/1991
Social Security number •••-••-2208
Driving licence — not held
Phone (512) 555 ‑ 0910
Email adaeze.o@example.com
First seen 04/02/2021
Only the last four digits are ever shown, on every screen in the product. The number itself is encrypted and the thing that matched it is a one-way token beside it — so the
match was computed without anybody, including this dialog, reading the identifier.
WHAT MATCHED, AND WHAT DID NOT
EVIDENCE YOU TYPED ON FILE AGREES?
Name Okonkwo, Adaeze Okonkwo, Adaeze Yes
R9 · the candidate, opened over the new account · /brazosbend/accounts/new?step=2&match=c-00412 · One dialog, opened from the panel, on whichever screen you are on
v2.234.15
SO
Sam Ortiz
Billing Clerk
Date of birth 03/14/1991 03/14/1991 Yes
Social Security number •••-••-2208 •••-••-2208 Yes
Driving licence — — Neither held
Phone (512) 555 ‑ 0164 (512) 555 ‑ 0910 No
Email a.okonkwo@example.com adaeze.o@example.com No
A phone will never make this a strong match, and it can open an account on its own. A person is identified for CREATION by a Social Security number, a driving
licence or a phone — and is RECOGNISED only by the first two.
THE ACCOUNTS THEY HOLD
ACCOUNT ADDRESS OPENED CLOSED STATE BALANCE
A-10744 219 Poplar Ave 04/02/2021 11/30/2025 Closed $0.00
A-11907 44 Willow Bend · Unit 3 12/04/2025 — Active $38.10
Deposit held $150.00 · on the closed account
Deposit interest — not recorded
Payments in four years 48 · none late
Ever disconnected No
Open complaints None
Deposit band this earns Waived — on this history
And the figure shown is not the figure agreed. The signed arithmetic for a deposit held this long is $153.50 — $150.00 with $3.50 of interest.
IF YOU LINK THEM
WHAT WHAT HAPPENS
The customer number Stays C-00412 — never a second one
This new account Becomes their third
The deposit Offered to carry, not moved automatically
Their history Counts against the deposit band
The old accounts Untouched — nothing is merged
The $150.00 is the whole argument. It is sitting on a closed account under this customer number and can follow them onto the new one instead of being refunded and re-
taken.
Linking adds a row to a link table and changes nothing else. No account is merged, no bill is reissued and no history is rewritten — which is what makes it safe to do.
UNLINKING, IF THIS TURNS OUT TO BE WRONG
Nothing in the product does it. A link made by mistake is corrected by pointing the account at the right customer, which exists; there is no screen that simply removes one and
leaves the account with nobody.
Not the same person Link to C-00412
ACC-S19

/brazosbend/accounts/a-10432/move-in?step=2
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
v2.234.15
Account A-10432 / Move-in ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Account A-10432
MOVE-IN
Who is moving in
Step 2 of 6 · Customer
Save & exit
✓ Find unit 2 Customer 3 Start & read 4 Account
preferences 5 Deposit 6 Review
The customer
Customer kind
A person ▼
Full name *
Miller, Sarah
Date of birth *
04/11/1988 📅
Phone
(512) 555 ‑ 0142
Identity
Social Security number
•••-••-4417
Driving licence
TX ••••882
One of these is required here, and that is a ruling rather than a form’s preference. On the move-in, verbatim:
"You either create new Customer ID or you link existing customer ID here".
This looks like somebody you already have
CUSTOMER NUMBER ACCOUNTS MATCH
Miller, Sarah · born 04/11/1988 C-00655 1 · closed Weak
Miller, S. · born 09/22/1990 C-00801 1 · open Weak
C-00655 Name and birthday agree · no identifier on file
C-00801 Name agrees · birthday does not
The same panel, and neither row is offered as the answer. The first was opened on a phone number four years ago and
holds no Social Security number or licence to compare against — so nothing can raise it to strong, however obviously it is the
same person.
Open C-00655 and see what they hold →
What weak means here, and what it
does not
STRONG WEAK
Shown to the clerk Yes Yes
Can be linked by hand Yes Yes
Carries a deposit across Yes No
Earns a deposit band Yes No
Money moves on a strong match and on nothing else. A clerk may still
link a weak one — and should, when they can see it is the same household —
but the $150.00 does not follow a guess.
So what should the clerk do
Link to C-00655 anyway
They know this household.
Ask for the licence and try again
One field turns this weak match strong, and the deposit follows on its own.
Create a new customer
The middle option is the one worth putting first in training. A driving licence
taken at the counter is thirty seconds, and it is the difference between a customer
being recognised and being charged a second deposit.
Two tiers reach this screen, not
three
PROBABLE IS IN THE VOCABULARY AND IS NEVER PRODUCED
The matcher emits strong or weak and nothing in between — probable is
described in the code as a human’s word. A screen that drew three bands
would be offering a middle one nothing can ever fill.
NOTHING SEARCHES FOR A NEAR-MISS ON THE ADDRESS
Two people at the same address with different birthdays are not compared at
all. The criteria are the name, the birthday and a government identifier; an
address is not among them and adding it would be inventing a threshold
nobody agreed.
←  Back Continue →
R9 · the move-in, and the match that cannot be strong · /brazosbend/accounts/a-10432/move-in?step=2 · A phone opens an account and never recognises anybody
SO Sam Ortiz
Billing Clerk
ACC-S19
/brazosbend/requests/new?step=1
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
v2.234.15
SO
Sam Ortiz
Billing Clerk
Requests / New request ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Requests
SERVICE REQUEST
Who is asking
Step 1 of 6 · Who is asking
Save & exit
1 Who is asking 2 Address &
property 3 Connection 4 Documents 5 Fees 6 Check & submit
Who is asking
Applying as
A person ▼
Full name *
Okonkwo, Adaeze
Email
a.okonkwo@example.com
Phone
(512) 555 ‑ 0164
How they came to us
At the counter ▼
This looks like somebody you already have
CUSTOMER NUMBER ACCOUNTS MATCH
Okonkwo, Adaeze C-00412 2 · 1 open Not judged
Name Agrees
Email Agrees
Date of birth — this form does not ask
Government identifier — this form does not ask
The same panel, and the verdict column is the one thing it cannot fill. A request form asks for neither a date of birth nor
a government identifier, so the criteria that decide a match cannot be assessed here at all.
Open C-00412 and see what they hold →
And nothing is created either way
WHAT THIS DOOR WRITES
One numbered request Yes
A customer No
An account No
A link between them No
That is deliberate and it was confirmed rather than assumed. A service
request is an ASK, not a party and not an account.
So the linking happens later
WHEN WHERE WHO
The request is
reviewed
The request record A clerk
It is approved
and fulfilled
Whichever door it
becomes
That door resolves the
customer properly
A request can be pointed at a customer on its own record, as the clerk’s act,
with the tier they judged. What it may not do is mint one at the moment somebody
fills in a form at the counter.
The flag still earns its place here. Knowing that an applicant already has
two accounts changes how the request is handled — whether a deposit is
needed at all, whether there is a debt on another address, whether this is the
third property of a landlord who should be on a master account.
WHAT IT MUST NEVER BECOME
A convenience that quietly creates the customer once somebody clicks the
row. The rule that this door writes one request and nothing else was pinned
precisely so a later change could not widen it by accident, and a screen is the
easiest place for that to happen.
←  Back Continue →
ACC-S19
R9 · the request capture, advisory only · /brazosbend/requests/new?step=1 · A door that creates nothing can only ever hint
CC S 9
/brazosbend/requests/new?step=1&match=c-00412
SMARTBillHub ☰
BB Brazos Bend Utilities
Dashboard
Plans & Rates
Premises
Assets
Accounts
Reads
Billing
Payments
Work
Finance
Runbooks
Reports
Settings
Requests / New request ⚲  Search accounts, premises, meters… ⚑ ?
▦
≡
⌂
▣
◉
▩
▤
▧
✦
▩
▦
▤
⚙
←  Requests
SERVICE REQUEST
Who is asking
Step 1 of 6 · Who is asking
Save & exit
1 Who is asking 2 Address &
property 3 Connection 4 Documents 5 Fees 6 Check & submit
Okonkwo, Adaeze · C-00412
What this customer already holds
✕
THE CUSTOMER ON FILE
Customer number C-00412
Name Okonkwo, Adaeze
Kind Person
Date of birth 03/14/1991
Social Security number •••-••-2208
Driving licence — not held
Phone (512) 555 ‑ 0910
Email adaeze.o@example.com
First seen 04/02/2021
Only the last four digits are ever shown, on every screen in the product. The number itself is encrypted and the thing that matched it is a one-way token beside it — so the
match was computed without anybody, including this dialog, reading the identifier.
WHAT MATCHED, AND WHAT DID NOT
EVIDENCE YOU TYPED ON FILE AGREES?
Name Okonkwo, Adaeze Okonkwo, Adaeze Yes
Date of birth 03/14/1991 03/14/1991 Yes
Social Security number •••-••-2208 •••-••-2208 Yes
Driving licence — — Neither held
Phone (512) 555 ‑ 0164 (512) 555 ‑ 0910 No
Email a.okonkwo@example.com adaeze.o@example.com No
A phone will never make this a strong match, and it can open an account on its own. A person is identified for CREATION by a Social Security number, a driving
licence or a phone — and is RECOGNISED only by the first two.
THE ACCOUNTS THEY HOLD
R9 · the same dialog, over the service request · /brazosbend/requests/new?step=1&match=c-00412 · Same customer, same dialog — and one button greyed with its reason
The piece Where it stands today What it costs
Judging a match Built. The ruled criteria, computed against encrypted identifiers through a one-way token. Nothing.
Resolving the party
at four doors
Built, and it already names the outcome linked / created / none. Nothing.
Showing the clerk
any of it
Not built. The outcome is dropped from the response before a screen sees it. The panel drawn above, and the key it reads already exists.
Offering candidates
BEFORE the commit
Not built. Today the resolution happens at save; these drawings show it while
the clerk is still typing.
A read endpoint that judges a block without writing anything — the
same criteria, no side effects.
The deposit that
follows a strong
Built, and gated on strong alone. Nothing — it needs the clerk to have linked them, which needs the
 l
v2.234.15
SO
Sam Ortiz
Billing Clerk
ACCOUNT ADDRESS OPENED CLOSED STATE BALANCE
A-10744 219 Poplar Ave 04/02/2021 11/30/2025 Closed $0.00
A-11907 44 Willow Bend · Unit 3 12/04/2025 — Active $38.10
Deposit held $150.00 · on the closed account
Deposit interest — not recorded
Payments in four years 48 · none late
Ever disconnected No
Open complaints None
Deposit band this earns Waived — on this history
And the figure shown is not the figure agreed. The signed arithmetic for a deposit held this long is $153.50 — $150.00 with $3.50 of interest.
WHAT YOU CAN DO WITH THIS, HERE
WHAT HERE? WHY
Read it, and judge the application Yes Two accounts and a clean history change what you ask for
Note it on the request Yes A sentence on the request, for whoever reviews it
Link the applicant to C-00412 No This door creates no customer and no account
The button is greyed rather than removed, and that is deliberate. Taking it away would make this look like a different dialog from the one on the other two screens.
Where the linking happens instead. The request can be pointed at a customer on its own record, as the clerk’s act with the tier they judged — and whichever door the request
eventually becomes resolves the customer properly at that point.
WHAT IT MUST NEVER BECOME
A convenience that quietly creates the customer once somebody clicks the row. The rule that this door writes one request and nothing else was pinned precisely so a later
change could not widen it, and a dialog with a live button on it is the easiest place for that to happen.
Close
Link to C-00412
ACC-S19
follows a strong
match
panel.
⚠  A phone opens an
account and
recognises nobody
Both halves are rules and both are correct. A person is created on a Social Security number,
a licence or a phone, and recognised only by the first two.
A decision, not code: whether a customer holding only a phone
should be prompted for more at the next contact.
⚠  Probable is never
emitted
The vocabulary has three tiers and the matcher produces two, which its own note states. Nothing, as long as no screen draws a band nothing can fill.
Unlinking a mistake Not built. An account can be pointed at a different customer; nothing removes a
link and leaves the account with nobody.
A decision about whether that state should exist at all.
Where the modules meet
Built from the ⇄ rows of the field tables above — the real cross-module surface
of this flow, from what the screens actually read rather than from what the
module map says they should. 13 cross-module facts reach these screens
across 6 boundary crossings.
The four questions, and which of them found nothing
Question Finding
1 · Does the handoff
land?
One gap, and it is stated rather than silent. The move-out assembles a final-bill handoff for a bill run to read, and MoveOutWizard.tsx:1384 says where it goes: "it
is assembled and returned, and it is stored nowhere: no table, queue or outbox exists for it, so it lives in this answer and in the audit row." Billing is the intended reader
and cannot read it.
2 · Does any module
write another's
tables?
Yes, once, mediated. See the seam table below.
3 · Does one fact
have two homes?
Yes, once — the ageing vocabulary. Every account row carries ageing_segment (customers' four bands, derived from opening buckets, served) beside aging
(billing's three-state display vocabulary, still null). Two names for one question about a customer's money. The backend lane reported it on 2026-08-24: when billing
publishes its version, one vocabulary has to win, and that is a ruling rather than a merge.
4 · Does the same
thing have two
names?
Nothing found in this flow. B14 rule 34 settles the one pair that used to drift — Recorded and In the books — and both appear consistently. Said explicitly rather
than left to be inferred from an absent heading.
Every crossing, graded on what the seam hands back
From To The shared fact What it returns Grade
customers portal Portal sign-in count,
lockouts, last sign-in —
the S21 Portal panel
A plain dict of derived scalars: {logins, locked, last_sign_in, unreadable}. Reads only.
portal_seam.py:85
HEALTHY
customers ledger Opening balances and
d i
Frozen @dataclass DTOs handed to ledger's own posting path. Clean boundary, but no seam file — a
di lik
HEALTHY, NO SEAM FILE
deposits at cutover direct from apps.ledger import, unlike apps/work/seams/. import_writer.py
customers metering An interruption raised
from a service request
It writes. service_request_api.py:907 calls interruption_service.create_interruption(...), and
metering/interruption_service.py:165 does Interruption.objects.create(...). Customers does not
call the manager — it calls metering's own service, so metering's rules run — but the boundary is crossed by
a direct import with no declared seam, and a customers request handler is what causes a metering row to
exist.
LEAKY · writes by effect
customers metering STORABLE_KINDS, the
tenancy service
catalogue
Imports metering's models module directly rather than through a seam. Reads only.
service_request_service.py
LEAKY
customers tenancy Lookup handler
registration
register_lookup_handler(...) — registration into tenancy's own extension point, which is what it is for.
lookups.py
HEALTHY
customers metering +
tenancy
Demo fixture seeding Not a product path. Listed so the count of six is honest rather than quietly six-minus-one.
 NOT GRADED
Both modules are named in every row on purpose — a finding filed against
one module is a finding the other module's owner never reads. The interruption
row belongs to the customers owner and to the metering owner, and neither
would find it in their own module's audit.
12
The specification register
One row per commitment, no exceptions. Every commitment appears both here
and as a card in the section that owns it. Status starts at Unverified for every
row and that is not a hedge — engineering fills the column in from the code,
one row at a time, and several routinely come back already done. Saying so is
what makes the column honest rather than decorative.
Why these IDs are new, and what the live series are
ACC-S1…ACC-S10 is a series minted for this document. It is deliberately not allocated into the repository's live series — OQ-, DEF-, CR-, US-, BR- — because an analysis may propose
and never allocate, and borrowing a live ID makes work look scheduled when it is not. Allocation in this repo goes through 10-scripts/allocate.py against the remote, and this
document did not run it.
ID Title, and what it waits on Screens What done looks like on screen Status
ACC-
S1
A clerk can correct an account's details without a wizard. Waits on nothing
server-side — PATCH /accounts/{id} is mounted, audited and tested. A client
wrapper and a form are missing.
02 An Edit control on the Account panel opens a form; changing Preferred
language to Spanish and saving shows Spanish on the panel and adds one
account.updated row to the Audit tab naming the field, the old value and
the new.
Unverified
ACC- The accounts list stays fast at forty thousand accounts. Waits on a decision: 01 On a 40,000-account tenant, sorting by Balance descending returns the Unverified
S2
The accounts list stays fast at forty thousand accounts. Waits on a decision:
materialise the derived positions somewhere sortable, or sort in SQL on the
four stored columns and say so.
01 On a 40,000 account tenant, sorting by Balance descending returns the
first fifty rows in under a second and the footer reads Showing 1–50 of
40,000.
Unverified
ACC-
S3
No screen tells a clerk the customer portal does not exist. Waits on
nothing — the portal shipped and DEF-CUS-4625 already fixed this on the
Overview.
02 Neither the Notes tab's Customer visible hint nor the Audit tab's portal-
actor hover contains the words "there is no customer portal in this version".
Unverified
ACC-
S4
Every date field behaves the same way. Waits on a shared .date-input
component, which does not exist anywhere in 07-frontend.
03 · 04 ·
08 · 10 ·
11 · 12 ·
13 · 14
Move-out step 2's Moved out on shows 08/31/2026 in the tenant's format,
accepts 08312026 typed in, and offers Today — identically on all eight
screens.
Unverified
ACC-
S5
The catalogue stops carrying sentences no screen shows. Waits on nothing
— every condition described was resolved.
01 · 02 Nothing changes on screen, which is the point. A grep for
accounts.arrives returns nothing outside the git history.
Unverified
ACC-
S6
A hold that has expired goes red instead of going stale. Waits on a
convention: a refusal written with a clock in it gets a test that fails when the
clock runs out, in the same commit.
01 · 02 ·
03 · 04 ·
08 · 12 ·
14
When the customer portal shipped, the suite went red naming
customers.account.note.customerVisibleInert — rather than that
sentence surviving on the Notes tab for an auditor to find.
Unverified
ACC-
S7
A close-out has a story that owns it. Waits on an epic. The act was ruled
2026-08-27, the screen was built the same day, and no epic covers it.
10 CloseOutPage.tsx's Story line stops reading "NO STORY OWNS THIS
SCREEN."
Unverified
ACC-
S8
An account can hold a document. Waits on the table BR-CUS-036 names and
an upload endpoint. Neither exists; no ruling defers them.
02 The Documents tab lists Tenancy agreement · Contract · 12/03/2026 · S.
Miller · 214 KB instead of drawing headings over a stated absence, and
Upload is not disabled.
Unverified
ACC-
S9
A finished import run can be reopened to fix its rejected rows. Waits on
nothing ruled — the copy says only "not switched on yet".
15 On a run reading 1,966 loaded · 34 rejected, a Fix rows action opens the 34
with their reasons, and correcting and re-committing them moves the run
to 2,000 loaded · 0 rejected.
Unverified
ACC-
S10
A cut cannot be scheduled before it is lawful. Waits on the notice-date-
plus-statutory-period calculation, rolled past weekends and holidays. Nothing
performs that roll today.
12 Disconnect step 3 shows Earliest lawful cut date: 05/14/2026, and the date
picker refuses anything before it with the reason visible on the disabled
cells.
Unverified
ACC-
S14
Every quick action on an account opens as a form over the account, with
all of its fields and a recap before it commits. Waits on nothing server-side
for nine of the thirteen. Adjust waits on a billing endpoint to post to; Send
statement waits on statements; the Record payment additions wait on an
open-bills call that already exists and on a late-fee figure that does not. R4 in
§10 draws all thirteen.
02 A clerk on the phone presses any of the thirteen, fills the form without
losing sight of the balance behind it, reads back a recap, and commits —
or reads why it cannot be committed, on the button itself.
Unverified
ACC-
S15
Every group on the Overview tab carries an edit control, disabled with its
reason where the group cannot be changed. Account waits on nothing —
PATCH /accounts/{id} is served and unwrapped. Plan waits on nothing — it
opens the Change plan wizard. Customer, mailing address and service
agreements each wait on one endpoint that does not exist. R5 in §10 draws all
six surfaces.
02 A clerk correcting a tax certificate, a phone number or a billing address
does it from the panel showing it, and every group that cannot be
corrected says why on the control itself.
Unverified
ACC-
S16
A clerk can write to the customer from the account, and see what has
already been sent. Waits on one endpoint: composing a message from an
 t E thi l i d th tb d it filt it f il d
02 A clerk on a collections call answers “what have you sent me” from the
account in one click, sees that the text message failed and the email did
 t d l ith t l i th
Unverified
account. Everything else is served — the outbound queue, its filters, its failed-
first sort, Resend and Requeue. The composer must queue rather than send,
refuse free text on a regulated step, and force the postal channel on a notice.
R6 in §10 draws both views.
not, and queues a reply without leaving the screen.
ACC-
S17
A master account lists every account at its address, with each one’s status.
Waits on no new table and, for the most part, no new endpoint: the covered
units are already computed for billing, the accounts at a premises are a filtered
account list, and the vacant-standby flag is already on the unit. The tab is the
work. R7 in §10 draws it.
02 A clerk on a call about a building sees what the owner bill prices, who the
tenants are, and that a three-month vacancy is costing the owner nothing
— without the screen implying the owner answers for a tenant’s arrears.
Unverified
ACC-
S18
A company customer names the master account it belongs under, and the
review step refuses a pick that disagrees with the address. Three parts,
three sizes. The SEARCH waits on nothing — the account list already filters to
master accounts and searches on number, company name and address. The
CHECK waits on nothing either: the derived master has been on the account
read since 2026-08-27. STORING a hand-picked master waits on a ruling —
the link is derived and deliberately stored nowhere, so a second answer means
deciding which one wins.
03 A clerk opening an account for a company picks which of that company’s
buildings it belongs under, is not blocked when the company rents and
has none, is stopped before recording a master that belongs to a different
building, and is told plainly that nothing is rolled up.
Unverified
ACC-
S20
Every wizard’s work has a queue, and the register’s ten tabs are where
they land. Seven worklists — requests, new connects, move-ins, move-outs,
transfers, disconnects, imports — each over a table that already exists, with the
columns those screens already declare. What is missing is not data: it is that
this document never drew where a clerk goes after pressing Submit.
01 A clerk who has just committed a wizard can find the thing they made, and
can see at a glance which rows they can actually move — because waiting
on is a column beside the state and not folded into it.
Unverified
ACC-
S21
Each queued record opens onto its own page, and the request’s five
outcomes are the link between them. The service request detail exists today;
the build, the two moves, the transfer and the disconnect case are proposed
and drawn from their own tables. Approving a request raises the job and the
job names the request it came from, with anything still owed on it travelling
along.
01 · 02 A clerk can answer what happened, what is it waiting on, and what has still
not been done from the record itself — including the cases where
completed does not mean finished.
Unverified
This table fills a gap rather than replacing one. This document had no such
index before; the repository's own indexes are 12-governance/01-open-
questions.md, 12-governance/10-defect-log.csv and 12-governance/11-change-
requests.md, and nothing here supersedes them.
13
What this pass changed, line by line
A changelog of the analysis itself, so a reader of an earlier version knows what
moved and — more importantly — what deliberately did not.
R5 GAINS THE UNIT, WHICH WAS THE ONE GROUP THE OVERVIEW NEVER SHOWED. Reported: "from the edit perspective, I cannot see the unit edit where I want
to change unit a to unit b." Correct, twice over — the Account group did not carry the unit at all, so there was nothing to hang a control on. It has a row now, and E07
draws the dialog: search and pick the new unit, then every aspect of both units side by side with each changing value marked — number, label, type, floor, area,
premises, address, map point, parcel, plan, plan lock, vacant-standby, meters and services. Two values that do NOT change are worth as much as the ones that do.
The service address is unchanged, because an address belongs to the building and both suites are in it: correcting the unit corrects the meters and the plan, and the
envelope looks identical. And the reading history does not follow — two years of reads stay with the old unit's meters, so this account's usage chart starts again, and a
clerk asked why should be able to say so. The commit is drawn disabled, because this collides with a signed rule. services.update_account refuses unit by name —
create-only, never patched — citing BR-CUS-017, and that rule is protecting the right thing: a customer who has MOVED must leave by move-out and arrive by move-in,
or the bills, meters and reads follow a person instead of staying with the property. But it also blocks a case the product has no path for at all: a record that named the
wrong unit, where nobody moved and the account has simply been billing against the wrong meters. Today the only way out is to close the account and open another,
which loses its history to fix a typo. The ask to the PO is narrow and is stated on the drawing: may an account be re-pointed at another unit as a CORRECTION —
with a reason, a supervisor, and issued bills left alone? Everything else about BR-CUS-017 stands.
THE WORK TAB IS ONE TABLE NOW, AND THE SORT IS THE FINDING. Ruled: "show only the work orders table, with all the search and filters." The Build table is gone
— the jobs that built this service are work orders like any other and were already in the list below it (WO-24-1902 is the meter set); the only thing that was not a work
order is the service application, which belongs to the premises rather than the account, and the drawing says so. Drawn against what the dispatch list really does. Six
filters — search, type, status, priority, technician, area — and a seventh comes back as an error rather than being ignored, which is the opposite of every other
list in the product and deliberately so: a dispatcher whose filter was silently dropped is looking at a wider list than they think and ticking rows on it. The sort is FIXED:
priority rank, then due time, with no column to click — so the list is not in date order and the footer has to say why, and an order with no priority set sorts LAST,
because a job nobody prioritised is not more urgent than one somebody marked Urgent. There is a Columns chooser because dispatchers and clerks want different
halves of the same row.
EVERY TAB'S PRIMARY ACTION IS RIGHT-ALIGNED NOW. Reported against Adjustments, Documents and Notes: "the action buttons must be on the right align."
They were not, and not by accident of those three tabs — .pw-tools is a plain flex row with no justification, so the toolbar's second argument simply sat after the first.
New adjustment, Upload document and Add note were wedged against the filter chips instead of at the end of the row. Fixed once in the shared toolbar rather than
three times, so all seven right-hand slots in the document moved with them — including All bills, the usage window, the meter sort and the work Columns chooser.
THE READ LOG THE METERS TAB POINTS AT IS DRAWN. The row action now has the dialog it opens: one meter’s reads over the tab it was opened from, with the
meter’s own facts at the top, a period and source filter, a search, and the log itself newest first. It is built from what GET /assets/{id}/reads actually serves — a
calendar date (never the raw instant), the channel, the register reading, the consumption with its explicit unit, the export half of a net-metering pair, the source and the
status. That payload carries no reader and no note, so neither is drawn, and the drawing says so rather than leaving a reader to wonder: an earlier cut of this
document had a Notes column on its read-log tables that nothing in the product fills. “Side gate locked” belongs to the work order, not to the read. The register
chains. Each reading less the one before it is the usage printed beside it, and the build refuses if it does not — so this log cannot disagree with the chart on the Usage
tab. The estimated read of 05/19/2026 ties to WO-26-3980 on the Work tab, and the note explains why the following month looks ordinary: the next real read absorbs
the difference.
THE METERS TAB IS ONE TABLE NOW. Ruled: "So only one table. That is the meters of this unit. Don't show any other tables. And for the read log, just put an action
there to view the read log for the particular meter. Build the search and filters for the meter table." It had carried four tables — the account’s services, the unit’s meters,
then a read log per meter, which on a unit with six meters would push the list itself off the screen. Now: one table, with a search box, service and status chips, a filter
menu and a sort control, and Read log as a row action served by GET /assets/{id}/reads. The services this account holds are a different fact and already have their
own group on Overview. Two columns that look alike are now both shown, because the codebase keeps them apart and a clerk needs both: meter type is what the
meter IS, read method is how the reading is COLLECTED. A row makes the point — W-4417 is an AMR meter still being read on foot. The filters are the ones the asset
register really filters on (service, status, meter_type, type, test_due), not invented ones.
Every paginated table in the document gained breathing room. Found while drawing the meters table: .pw-pg shares its border and padding with the filter chips,
which are inline things carrying no block margin — so on every tab the row count sat flush against whatever note followed it. One rule at the end of the sheet, and all
of them are fixed.
USAGE: A TABLE ON THE OVERVIEW, A REAL CHART ON THE USAGE TAB. Two instructions, and they pull in opposite directions on purpose. On the Overview the
Usage trend group is now a plain month-by-month table — six months, electric and water side by side — because a summary panel a third of a screen wide is a poor
place for a graph and a good place for figures a clerk reads out. On the Usage tab it is a proper bar chart: twelve months, an axis, a labelled value on every bar and the
month beneath it. The chart computes its own geometry from the data, so a bar and the number printed on it cannot disagree, and the stats beside it — average
5 140 kWh highest 6 820 in Dec 25 lowest 3 960 in Feb 26 are worked out from the same twelve numbers rather than typed in
5,140 kWh, highest 6,820 in Dec 25, lowest 3,960 in Feb 26 — are worked out from the same twelve numbers rather than typed in.
The chart was built twice, and the first way was wrong twice over. Worth recording because neither fault announces itself. It was first drawn as inline SVG, with
colours in presentation attributes — fill="var(--p-n600)", which is not valid: var() is a CSS value function and a presentation attribute is not CSS. Every label laid out
correctly, reported a sensible getBBox(), and painted nothing. Moving colour into style fixed the paint and revealed the second fault: every drawing in this document
is transform-scaled to fit the page, and SVG text inside a scaled subtree renders shifted and clipped while the shapes around it stay put — labels landed beside
the wrong bar, cut mid-glyph, while the bars themselves were perfectly placed. It is built from HTML elements now, which scale with the transform like everything else.
A screenshot found both; no check in this document could, because a label painting nowhere still passes every geometry probe it has.
ALL TWELVE TABS ARE NOW DRAWN WITH A FULL ACCOUNT BEHIND THEM. Reported: "I can see in the wireframe that there is no data on that screens... So please
add the data there. All screens should show data properly. If there is no data available, then add mock data properly according to the fields." Fair — A-11812 has almost
nothing on it in the seeded database, so eleven of the twelve tabs were an empty state, and an empty state shows a reader nothing about the layout. The rule they are
drawn to is: mock the data, keep the behaviour. Rows, amounts, dates and references are invented and every drawing carries sample data in its corner, so no figure
is ever quoted back as a finding. What the product can and cannot work out is NOT invented. The five bills carry real tax arithmetic, the three unpaid ones total exactly
the $2,410.00 in the header — and every one still reads Issued rather than Overdue, because past-due is not computed on this deployment and drawing it would
promise a build that cannot be delivered. Every absence no amount of data would fix stays: adjustments have no endpoint, documents have no upload, an audit row
has no link back, usage behind a bill is not summed. The rows on those tabs are drawn and labelled the shape, not the state.
R4 — EVERY QUICK ACTION AS A MODAL FORM, 13 MORE WINDOWS. Asked for directly: "build the modal form for the quick actions … show the full screen, and in
the screen show the model form open … each and every quick action should show in the model form with proper fields and details." Each drawing is a whole desktop
window with the account dimmed but readable behind the dialog, and each carries every field rather than a first step — six of the thirteen are multi-step today, and
the as-built drawings can only show step 1 of each. Five things are drawn that the product does not do: a confirmation on Activate account, which commits on the
click; a unit search on Move-in, which has no picker at all; the late fee, the available credits, the bill-by-bill allocation and the outstanding remainder on Record
payment; the bill carried across into Issue credit; and a recap as the last step of all thirteen. Registered as ACC-S14.
A rail that was drawing nothing. The step rails added with the action drawings used <span class="st"><i>1</i>… where this document's stylesheet declares .bdg and
.lb — so the numbered badges rendered as bare digits and the labels did not wrap. It is the same shape as the product bug this document files against B14 rule 21: a
class no sheet declares is not an error anywhere, it is simply nothing on the screen.
THE EDIT CONTROLS WERE BUILT AND COULD NOT BE FOUND, AND THAT IS TWO FAULTS. Reported: "The edit icon is not visible in the account details overview
tab." Both were mine. Placement: the drawing existed, in R5, one section away — and the signpost pointing at it had been dropped in after the Audit tab, eleven
drawings past the Overview it describes, which is no signpost at all. The Overview tab with its edit controls is now the drawing immediately after the as-built Overview,
where a reader meets it without being told. It is shown in both places from one source: here where you look, and in R5 where the commitment card owns it. Visibility:
the control was drawn as a plain accent link. At 12px, in a heading already full of accent-coloured text, a link reads as decoration — and the disabled ones at 45%
opacity read as nothing at all. It is a bordered control now, with a hit area: solid edge where it is live, dashed where it is refused, same size and same place either way.
R5 — AN EDIT CONTROL ON EVERY GROUP OF THE OVERVIEW TAB, 6 MORE WINDOWS. Asked for directly: "in the account details, in the overview tab, give edit
icon for the account service, customer plan, mailing address, these all sections and edit option." Eleven groups get the control; five are live, Plan opens the Change plan
wizard rather than duplicating it, and five are disabled with their reason. The product already ships this pattern in exactly one place — the Payment method panel’s
→ Update method, drawn and disabled with its reason — so R5 is that decision made general. Two of the eleven need no new server work at all: Account wraps PATCH
/accounts/{id}, which is served, tested and has no caller, and Plan links to a route that already runs. Registered as ACC-S15.
THE ACCOUNT HEADER IS NOW DEFINED ONCE AND USED EVERYWHERE. Reported: "please ensure on all these tab header is same - the way we have shown on
02". The tab, action and modal drawings each carried their own shortened copy — two pills instead of five, the address as a bare icon, and no service overflow — so
one screen was drawn three ways. All 32 now render the ratified header: kicker, name, the five state pills, one address line carrying the premises glyph, the service chips
with + 9 more, then the six actions. It is a single function in the drawing library rather than three copies, because a header copied is a header that will disagree with itself
— which is exactly what happened.
R6 — A COMMUNICATION ACTION ON THE ACCOUNT, 2 MORE WINDOWS. Asked for directly: "add a communication action to the quick action sections. here the
user can send quick communication to the customer." An eighth rail icon, and the dialog behind it in two views: write a message, and what has already gone out —
the second because the first thing a customer asks on a collections call is what they have already been sent, and on this account that is three notices in one fortnight,
one of which failed. Three product rules shaped the form rather than decorating it. Nothing is ever sent from a screen — the output of every notice path is queue
rows and there is no SMTP, ESP or print-vendor call in the module — so the commit reads Queue the message, not Send. Free text does not exist on a regulated step,
because the tone IS the tier, so the message box is refused with its reason the moment a reminder or a notice is chosen. And a text message supplements a letter
rather than replacing it, so on a regulated kind the postal channel is ticked and cannot be unticked. What already exists: the outbound queue, its search and filters, its
ratified failed and bounced first sort, Resend and Requeue. What does not: composing a message from an account — there is no ad-hoc send path anywhere in the
module, and that single endpoint is what ACC-S16 asks for.
THE NEW-ACCOUNT WIZARD LOSES ITS PLAN STEP: SIX STEPS BECOME FIVE. Ruled: "after selecting a unit on the service address, there should not be any step to
select a plan as plan is already attached on the unit itself. So whenever the unit is selected, show all the details." The product already agrees with the premise and
draws the wrong conclusion from it. Its Plan step carries no input at all, displays one derived value, and says so in its own copy — "the plan is read from the unit and
is not stored on the account", "shown, not stored" — then warns "pick a unit first if this reads empty". A whole step of six whose content depends entirely on the step
before it. It is a panel on the unit step now, and that step carries the unit's whole record: number, label, type, floor, area, premises, service address, map point and
which of the two points it is showing, parcel, plan with its version and lock, base charge, vacant-standby billing, meters and services. The clerk sees what the account
will inherit before committing to the unit rather than two clicks later. Rails renumbered, ?step= addresses shifted, and the section now says on its face that these five
drawings are the wizard as it should be rather than as it is. The same ruling was applied to the two dialogs that still offered the choice — Move-in's step 4 is
Deposit now rather than Plan and deposit, and Activate account shows the plan and its base charge as facts. In both, the plan is read from the unit and there is nothing
to pick.
BILLING PREFS BECOMES ACCOUNT PREFERENCES, WITH PAPERLESS ON IT. Ruled: "Make it as account preferences in that user can also select paperless billing. that
should also be available." The columns were already there and already read — paperless and sms_reminders are on accounts, are in the wizard's own create set, and are
resolved by delivery_channel_election_for_account. What was missing was the control. The step is now grouped under four headings — how the bill is delivered,
paying, tax, language — instead of one ungrouped column. And one fact on it is the reason it needs words rather than a tickbox. BR-BIL-036 makes print the floor:
paperless and text reminders are channels elected ON TOP of the paper, and neither can switch a bill's print row off. A clerk who ticks paperless and tells the customer
“no more paper” is wrong, and nothing on the screen would have told them — so the form says it in those words. Both default to off because, in the model's own
words, not electing is the safe answer. One thing corrected in passing: the tax-exempt expiry read 31/12/2027 on a screen whose every other date is MM/DD/YYYY in the
tenant's own timezone. It reads 12/31/2027 now. A rendering fault found while drawing it and fixed everywhere: a ticked box was being emitted as an empty .bx.on,
which the sheet paints as a solid block with nothing in it — it reads as a filled square, not a ticked box. The tick is a character the markup has to supply. Twenty-three
checkboxes across the document were drawing wrong; a screenshot found it and no structural check could, because an empty span is perfectly well-formed.
THE DEPOSIT IS TAKEN INSIDE THE NEW-ACCOUNT FLOW NOW. Ruled: "if there are deposits, then there should be a proper flow to accept those deposit also … you
figure it out where … but it should be in the same flow." The deposit step collected nothing at all before this — its own caption said so: "nothing on this step is collected."
Where it goes has only one answer. A payment posts against an account, and the account does not exist until the last step commits it. So the money cannot be
TAKEN on step 4 — but it can be CAPTURED there, beside the deposit it pays, and WRITTEN on the commit. Step 4 now asks whether a deposit is due, how much and
why, and whether the customer is paying today, with method, reference, posting and clearing dates. Step 5 shows the three writes in order — create the account,
activate it if chosen, then post the deposit through the same path Record payment uses — and says what to do when the third one fails: the account stands, the
deposit is unpaid, and the clerk lands on Record payment with the details already filled in rather than being asked to retype them. And it carries the trap this
document has already caught live. A deposit reaches the deposit register only when its payment CLEARS. Leave the clearing date blank and the new account reads a
deposit of $0.00 while the cash is in the drawer — correct, and it looks wrong. That is the same fault as PY-260911-0076, $500.00, still Processing on Bramble Bakery
with the balance unmoved. The form says it where the clerk is about to do it.
THE REVIEW STEP RECAPS ALL FOUR STEPS, AND THE ACTION MOVED TO THE BOTTOM. Ruled: "each and every details properly from each and every step. The
deposit details also show properly. The payment of deposits also show properly … and move the save as actions, draft and activate at the bottom." It had been recapping
eight facts out of roughly forty, with the Save-as chooser sitting at the TOP of the step — the first thing read and the last thing decided. Now: five groups, one per step
plus the deposit and its payment split apart, every field carried across, each group linking back to the step that owns it, and a closing summary of what will be on the
account the moment it exists. The chooser is at the bottom, as a dropdown per the standing radio-to-dropdown ruling, with the consequence of each option written
beside it — draft occupies nothing, activate takes the unit — and the commit button names what it will do. It also repairs something this pass introduced. The unit
panel added to step 2 described Bramble Bakery's Suite 2 while this wizard's account is Miller, Sarah at 1408 Elm Street · Unit A — a sample lifted from another drawing
and never reconciled. It describes the right unit now, and keeps the meters the step already named. Worth recording rather than quietly fixing: nothing in the document
 ld h ht it b b th l i t ll i t t d l di d ith h th
would have caught it, because both panels were internally consistent and only disagreed with each other.
THE MOVE-IN WIZARD'S FIRST STEP GETS A REAL SEARCH, AND THE UNIT'S WHOLE RECORD. Ruled: "there should be a proper search and select field. And after
selecting, show the unit details below the field. All the unit details should be visible clearly." Asked for three times, and until now it had only been built in R4's move-in
DIALOG — the wizard itself still opened on five read-only facts with no field to type in at all. Mine to own: the ruling named the wizard and I had fixed the dialog. The
step now searches vacant units, lists them with a taken one shown and refused rather than hidden, and opens the chosen one into four groups — the unit, what it is
billed on, its services and meters with their last reads, and who was here before. Two things on that panel earn their place: the meters' final reads are what become
the new occupant's opening reads on step 3, and the vacancy length is called out, because nothing has been read at this address since January and the opening reads
are three months old. Why the product has no picker, so this is not mistaken for a bug fix: the account-scoped move-in takes the unit from the account in the
address bar, and sending a unit with that call would be a second answer to a question that already has one. This step is the OTHER door — a clerk starting from Move-
in has no outgoing account to inherit from. Both reach the same wizard, so the step says which one it is on. Dates on the section were also DD/MM on a screen that is
MM/DD everywhere else.
R7 — A MASTER ACCOUNT SHOWS WHAT IT COVERS. Ruled: "if the account is of master account, then after the overview tab, it should show the accounts that are
connected to that master account." A thirteenth tab, shown only when the kind is master, immediately after Overview. “Connected” is not what it sounds like, and the
obvious drawing would have invented a relationship the product does not have. A master account is an ordinary account row with one column set; the payer is
the premises' owner and it is attached to the common-area units. There is no parent, no children and no rolled-up balance. So the tab keeps two things apart rather
than drawing a tree: the units it covers — a real linkage through its own service agreements, and what one owner bill prices — and the other accounts at the
address, related by address only. The tenant on the drawing owes $186.40 and the owner does not, and the screen says so, because a tree would quietly imply
otherwise. The figures are the product's own: 1408 Elm, $41.20 + $28.40 = $69.60 on one owner bill — and the read behind it exists because billing once priced the
anchor unit and nothing else, which is right for an ordinary account and two-thirds right for a master. The third block is the one clerks get wrong: a vacant unit
bills the owner only where that unit's own vacant-standby flag is set. Unit A has been empty ninety-four days and costs this owner nothing. Registered as ACC-S17.
R8 — A COMPANY CUSTOMER AND THE MASTER ACCOUNT IT BELONGS UNDER. Ruled: "Don't add any account selection there. Just keep the customer kind only. If
the user selects company, then ask user to select the associated company master account. where user can search and select it." The account-kind chooser drawn in
version 41 is withdrawn — the three-way selection, the master branch of the wizard and the second-master refusal are all gone. Customer kind is the only branch on
the step. ⚠  AND THE CORRECTION THAT MATTERS MORE THAN THE FIELD: version 41 told the PO there is no such thing as a sub-account. THAT WAS
WRONG. There is a parent-child link between accounts, it is called a sub-account, and the PO ruled it on 2026-08-27 — an occupying account is a child of the
premises' owner account. It is live under that name on the account read and on the move-out screen. What is true is narrower and was stated as if it were the whole
thing: there is no sub-account KIND and no stored link. The link is DERIVED and stored nowhere, which is why no column exists — a design, not a gap: a closed
tenant drops out of the list the day they close and a pending one never appears, so nobody has to remember to unlink anything. That makes the requested picker a
collision rather than an addition. The same day the link was ruled, the way the owner is found was superseded — it used to be inferred from who pays for the
hallway, and the PO replaced all of it: the premises names its owner, the owner is the master, nothing is inferred. The old reading was retired rather than kept as a
fallback, and the stated reason is the exact hazard a free picker reopens: a fallback that disagrees with the declared owner would silently bill a different party. The
move-out screen follows the same rule from the money side — its master arrives resolved from the server and there is no free-text account field, so a forged transfer is
unrepresentable rather than merely rejected. So both are drawn: the picker exactly as asked, with the three states a clerk meets — a company with several master
accounts, which is why it is a search; a company with none, because a company that rents owns no building; and the picker open. Then the review step, where both
answers are in hand for the first time: a pick that AGREES with the service address reads as a confirmation, and a pick that DISAGREES is stopped, with the two owners
named and three ways out — one of which is not on this screen at all, because a wrong declared owner is fixed on the premises. The search half needs nothing built
and neither does the check. Storing a hand-picked master is the part that waits on a ruling, and the open question is not the column but which of the two answers
wins when they differ. Registered as ACC-S18.
TWO CORRECTIONS TO R7, BOTH MINE. The callout said the six balances were "five separate debts owed by five separate people". They are not: two rows are $0.00
and one of the six IS the master, so the $810.95 is the owner's own $69.60 plus $741.35 owed by three tenants. The corrected wording had been written into the
generator and the wrong sentence left standing in the callout, so the document was carrying both at once — worse than either. And R7 described a master as
anchoring on the first common-area unit; that was superseded on 2026-09-01, when the row began hanging off the ADDRESS with no unit at all and reaching the
common areas through service agreements like any other covered unit. The money is identical either way — $41.20 + $28.40 = $69.60 — which is exactly why no
figure check could have caught it.
g g
THE MOVE-IN'S STEP 3 TAKES A READING, A READ DATE, OR AN ESTIMATE — DRAWN IN §04 ITSELF. Asked: "On the third step, start and read. The user can add
the read and read date. And if not, then he can estimate it." Then, on where it goes: "update those wireframes only. Do not add any r nine." So the move-in's own step-3
drawing is updated in place and no section was added — the drawing count is unchanged. Two of the three are already built. The READING has been collected since
2026-08-26, one row per readable register, each box pre-filled with that meter's last reading and its age; anything left blank sends no row at all rather than a zero. The
ESTIMATE is built too — "the meter could not be read" per register, which clears the value and locks the box, because a meter cannot have both a reading and be
unreadable. The READ DATE is the one that is missing, and it is missing entirely — the draft row is a meter number, a value and the tick, with no date field
anywhere, so every reading takes the service start date. The door has taken a per-row date all along and falls back to the event date when none is sent, so the
column costs no endpoint, no contract and no migration. The cost is a GUARD, not the column, and the drawing says so as a stated absence: the locked rules catch a
duplicate reading and a negative period, but nothing checks a read date against the previous occupant and no rule refuses one dated after today — while the start
date directly above it has both, on the screen and again on the server. An estimate can also refuse, in five named ways, and the drawing shows the demand register
doing it: a demand peak is never estimated, because the charge it drives would be disputed. ⚠  AND TWO SENTENCES ON THIS STEP ARE FALSE TODAY — "the date
is the whole of what this step stores", rendered directly above the capture table, and "no reading is taken from them here", rendered directly below it. A third, shared with
move-out, tells a move-in clerk that "the figure you leave is the one that closes the account". The step's title was rewritten when the capture landed; the hints under it
were not. Three string edits, worth making whether or not the date column is ever built.
§04'S MOVE-IN STEPPER: FIVE STEPS BECOME SIX. Ruled: "on the plans and deposit step, change the plans and deposit step to account preferences … and add one
more step of deposit into the move in stepper and copy the deposit step also. from the new account." The rail now reads Find unit · Customer · Start & read · Account
preferences · Deposit · Review, and all six drawings carry it. ⚠  AND IT CLOSES A CONTRADICTION THE DOCUMENT HAD BEEN CARRYING. Step 1 already said
the plan is inherited from the unit and is not a choice on any later step, while step 4 was called Plan & deposit in the rail and Plan & preferences in its own heading —
three names for one step, one of them promising a choice the wizard does not offer. Renaming it settles all three, and the plan now appears on that step only as a
stated absence saying where it really lives. The two copied steps do NOT have the same standing, and the drawings say so. Every account preference is genuinely
writable on a move-in — the move-in payload is the create payload minus the unit, so paperless, text reminders, autopay, tax exemption and language are all the same
columns a counter sign-up writes. The deposit is writable on no path at all: every deposit field is a refused input naming its own rule, so this step stands exactly
where the new-account wizard's does and carries the same absences rather than implying the move-in path is further along. It is not. One question is a move-in's
own, and it moved here from the old step 4 rather than being invented: a mover may have held an account with this utility before, so their own deposit could follow
them — and carry-forward rides the customer linkage, so there is nothing to read a prior position from. The drawing also says plainly that this is the CUSTOMER's prior
account and not the one being moved out of, whose deposit settles on its own close-out. The review recaps what the two new steps collect — the delivery elections,
the language, the deposit and the payment taken — since a wizard that takes $150 and then reviews nothing about it would be the obvious hole.
§04'S REVIEW RECAPS EVERY FIELD FROM EVERY STEP. Ruled: "update the review step. Each and every details should be visible on the review step. Each field details
from each step should be visible." The recap now carries the unit and everything it carries, the customer with their identity and mailing address, the start date with all
three register rows, the five preference elections, the deposit and the payment taken, and what the commit will and will not write — each block naming the step it came
from. ⚠  AND PUTTING EVERY FIELD ON ONE SCREEN IS WHAT EXPOSED FOUR CONTRADICTIONS BETWEEN THE STEPS — three of them this document's
own. A recap is a consistency check: values that had never met each other now sit four lines apart. (1) The same date written two ways in one wizard — step 1's
vacant since 01/29/2026 against step 3's earliest start 29/01/2026. The previous pass read this backwards and "converted" a copied deposit date to match the stray;
section 04 is month-first like the rest of the document, which its own vacant for 94 days confirms, so both the stray and the conversion are corrected. (2) A third meter
that does not exist — step 1 lists two meters on the unit and step 3 had grown an M-4023 for the demand register. A demand peak is a CHANNEL on the electric
meter, so it is M-4021 · demand. (3) Readings that contradicted the prior reads they continue — step 1 states the outgoing finals, 41,607 electric and 8,902 water,
and says in its own words that they become the opening reads on step 3; step 3 carried 48,209 and 1,204. The first implies 6,602 kWh drawn through an empty flat and
the second runs the register BACKWARDS, which is the negative-usage integrity rule this document described one pass earlier. Now 41,680 and 8,902 — ninety-four
empty days of standby and not a drop of water. (4) A note describing a date it no longer named. The lesson is the recap itself: none of the four was visible while
each value sat on its own step, and no structural check can see any of them.
§05'S SERVICE-REQUEST CAPTURE: FIVE OF ITS SIX STEPS REBUILT. Ruled: services on the connection step, a structured service address and a unit count under it,
the plot removed from the property step, documents actually attachable, the fee taken on the fees step with its payment summary, and a check step that shows
everything. Most of it is already built, which is the useful half of the answer. SERVICES are a table per request, each with its own requested start — so the
 i i MULTISELECT h l hi ili i h h i k d li d d h i h i d E h l h il bl fl
connection step is a MULTISELECT over the eleven this utility runs, with the picked ones listed underneath carrying their own start dates. Each also has an available flag
whose NULL means NOT YET ASKED, a real third state that is neither yes nor no; nothing on this wizard sets it, so a service picked here is a request and never a promise.
DOCUMENTS have a real attach path recording the type, name, size, uploader and time against a closed vocabulary of eight designed types plus Anything else — with
two deliberate gates: a missing document never blocks CREATION, and attaching a file is not verifying it. FEES AND THEIR PAYMENT are ruled: quoted, settled by an
invoice, collected at the counter, and outstanding = quoted − settled − collected, signed and never clamped at zero. Collection takes cash, card or cheque, REFUSES
without a receipt number — cash with no receipt is cash nobody can reconcile — snapshots the quote so a later line cannot retro-change what a receipt was handed
over for, and is idempotent on that receipt. The worked case is the one that raised the defect behind the rule: quoted $130.00, collected $25.00 cash on RCP-26-4471,
outstanding $105.00. ⚠  AND THE FEE STEP TAKES MONEY AND POSTS NOTHING — no journal line, no invoice, no account, because there is no account yet. The
counter accepts it and finance reconciles it, which is the ruling in the PO's own words and the reason this screen can exist before an account does. Two things are NOT
built and the drawings say so instead of implying otherwise. The service address is ONE verbatim field today, not five, kept exactly as the applicant gave it and
never overwritten by whatever the resolver matches — five boxes is five columns. And NOTHING holds a unit count. There is also no file STORE: the attach path records
a reference to a file this product does not hold, so the old wireframe's "no file upload path yet" was wrong in one direction and right in the other. The service address
and the unit count sit on the ADDRESSES & PROPERTY step, captured once and nowhere else: what the applicant wants is asked first, where they want it second.
The register match is shown beside the address there — evidence, never a decision, and never written over what they said. And the plot leaves the SCREEN while
keeping its COLUMN: removing a control is not dropping a column, and the drawing says which of the two happened.
§06'S NEW-CONNECT WIZARD: NINE STEPS BECOME EIGHT, AND THE PREMISE STEP CREATES THE SERVICE ADDRESS. Ruled: "merge the first and second step.
On the premise step, there should be the premise step and below the address of that premise will service address. Use the same service address fields only." The rail now
reads Owner & scope · Premise · Units · Map services · Plans & work orders · Charges · Communication · Review & confirm, and all eight drawings carry it. The
merge reads as one question rather than two: the scope decides how many units the later steps ask for, and the owner is who they are created against. Step 1's own
alert — "this build has no home yet, the premise arrives at step 3" — moved with the renumbering. ⚠  AND THE PREMISE STEP IS THE ONE SCREEN IN THE
PRODUCT WHERE TYPING AN ADDRESS CREATES THE RECORD EVERYTHING ELSE DERIVES FROM. An address is kept on the premise and nowhere else; every
meter, account, route, cycle, bill and work order reaches it by walking back. So these five boxes are the same SHAPE the request wizard asks for, and not the same KIND
of fact: a request keeps what the applicant said, verbatim and never overwritten, because it is not a premise yet. This one is. ⚠  ONE OF THE FIVE CANNOT BE
HONOURED HERE AND IS DRAWN DISABLED RATHER THAN DROPPED. A unit refines its building by LABEL and never by an address of its own — typing a unit
onto the building record is exactly the second home for an address the rule exists to prevent — and the units are created on the very next step. A control a screen
cannot honour renders disabled with its reason and is never hidden, so the box stays, greyed, saying where units are named. Dropping it would have made the address
set silently different from the one it was told to match.
§06'S MAP-SERVICES, CHARGES, COMMUNICATION AND REVIEW STEPS, REBUILT. Ruled: services pickable per unit as well as for all units, the charges payable on
their own step with every field, a communication step where the clerk chooses what goes out and searches for the template, and a review showing every field plus what
happens next. Per unit is not an alternative shape — it is THE shape. One row per unit per service is what the product stores, each with its own state and activation
date. Apply to all units writes exactly those rows, faster. The grid is drawn with it UNTICKED because that is the case the PO says is missing, and the common area is
why it matters: it takes electric and water and no sewer, which "all units" cannot express — a build that used it would raise a service point, a meter and a work order
for a drain a car park will never need. The charges step can take money because of a ruling that made one money path. Charges are tagged to an account number;
the step offers three debtors and only the owner's account names a party that exists at confirm. A charge floating on the build would have needed a second, parallel
money path — a payable that is not an invoice, settled by a payment referencing no account. ⚠  AND THE ONE THING BLOCKING IT IS A REASON THAT EXPIRED.
The path that attaches a payer refuses because an account must name a unit, and the owner's account is for the whole build. On 2026-09-01 an account stopped having
to name a unit: a Master Account hangs off the ADDRESS with no unit at all, which is exactly the owner's account for a whole build. The blocker is stale, not the
requirement — and it is the only part of this step that is a code change rather than a screen. Communication is queued and never sent, which the step says rather
than implying otherwise, and a template is chosen along three axes — the class of letter, the customer category and the language — falling back to the default variant
on the last two. Draft versions are LISTED and cannot be picked: hiding one sends a clerk looking for something they can see exists; offering it would queue a letter
nobody approved. The review's seven counts are a CONTRACT, not a summary — the commit must produce exactly them — and the step ends with what happens
next, including the three things this build will NOT do: it opens no accounts, sends nothing, and energises nothing. ⚠  AND IT RECONCILES A CONTRADICTION THE
DOCUMENT HAD GROWN. Section 06 said this build has TWELVE units while the record drawn for it says SIX, and the request that raised it says six too. Six wins — six
places against two — and every derived figure is recomputed from it: 20 service points, 20 meters, 7 plan assignments, $3,030.00 quoted.
p g y g p p , , p g , $ , q
WHERE EVERY FLOW'S WORK LANDS — THIRTEEN DRAWINGS, EACH BESIDE THE WIZARD THAT MAKES IT. Asked first for the missing list and detail views,
then: "these wireframes should be in their respective process section … So a user who is reading this document will read this with a flow." So there is no section of their
own. Each pair sits immediately after its wizard, and the document now reads the way the work happens: the steps a clerk fills in, the queue it joins, the record it
became. The gap was structural. Every wizard here ended at its commit step — twenty-nine wizard screens across six flows, and not one drawing of the queue the
work joins, so the document could not answer the first question a clerk asks after pressing Submit. They all land in ONE screen: the accounts register has ten tabs and
seven of them are these worklists. Every one has a real table behind it and the columns drawn are the ones those screens already declare. ⚠  AND THE SEVEN ARE
NOT SEVEN UNRELATED QUEUES. A service request carries an outcome, and the five job outcomes are exactly the other five flows. Requests is the front door; the
other five are what a request BECOMES — approve SR-26-0001 and a build appears on the next tab, naming the request it came from, with the $105.00 still
outstanding travelling along. That idea is placed with the Requests pair, where a reader meets it, rather than repeated at all seven. The new account wizard is the one
flow whose landing was already drawn: what it creates is an ACCOUNT, landing in the register's first tab and opening on screens 01 and 02. There is no separate
"new account request" object, and inventing a queue for one would be drawing a table the product does not have. Only one of the six records exists today — the
service request detail, three tabs, and the drawing follows it. A move-in's record is deliberately short and says why: a move-in is the record of an act and the thing it
produced is an account, so this page answers the day itself — and that completed does not mean finished, since one register opened with no figure at all. A closed
move-out can still be waiting on a decision: $186.40 owed by somebody who has left, nothing preselected, because a default would be the product deciding whose
debt it is. Registered as ACC-S20 and ACC-S21.
THE BUILD'S RECORD IN FULL, AND WHAT EVERY RECORD'S ACTIONS DO — EIGHT NEW DRAWINGS. Ruled: "Please add everything that is captured in the new
connect form. Each and everything should be visible … Also on that actions, what will happen? That wireframes should also be available below that screens only." The
build's record now carries every field the eight steps collected — owner and scope, the premise with its full address and parcel, the per-unit service grid, plans and
work orders, the three charge lines with what was taken and what is outstanding, every queued communication with its template and version, where it came from, and
its live state. One page, not tabs, because the point is that it is all visible. Eight actions are real and TWO RECORDS HAVE NONE — which is itself the answer. A
move-in and a transfer are records of acts that have already happened; there is nothing left to decide, so the only controls are doors to the accounts they produced,
and drawing a button would invent a decision the product does not offer. Every action drawing says what will happen, in a table, before the button. APPROVE
resolves a request to one of five outcomes with nothing preselected — the resolver's match is evidence, not the decision — and is held while two required documents
are unchecked. REFUSE is terminal and reopenable, and says plainly that it does not undo the $25.00 already taken. ASK FOR MORE keeps the request open and moves
waiting on to the applicant. ACTIVATE UNITS shows why each unit cannot go live — a gate not passed is a different job from no meter at all — and states two things a
clerk needs: that activation is terminal, and that the gate is not the same order for every service — gas gates on the LIGHT-UP, not the meter set, because
gating gas on the meter set energises and bills a customer who has no gas. ADD A WORK ORDER raises an ad-hoc job that gates nothing unless somebody says so. TIE
THE SHORTFALL BACK has no account box at all: the target is resolved by the server, so a forged transfer is unrepresentable rather than merely refused — and the
consequence, that the reminder ladder starts pointing at the landlord, is on the screen before the button rather than in a letter afterwards. MARK AS CUT re-asks the
four protections on the day, because an answer from when the notice went out is five days old — and says what it is not: the account does not close, the debt does not
move, and billing keeps running.
INTERNAL REFERENCES OFF THE SCREENS, AND THE PROSE CUT TO A BUDGET. Ruled: "look for internal data references, content sizes - it should be reduce and
meaningful", then "fix all". Seventeen internal references were leaking onto eight screens, almost all of it in the two wizards this pass never rebuilt. Rule ids and
question ids printed as field values; a module path handed to a clerk as the explanation of a figure; source files with line numbers in a screen's own copy; endpoint
paths in a dialog footer. None of it was a database id as a value — that rule has held everywhere — this was the other one, no rule id or internal code in clerk-facing
copy. Each is rewritten into the clerk's language and the citation moves below the drawing, to the caption, where every other screen already cites. A guard now
refuses any of the six patterns inside a drawing. ⚠  THE CONTENT SIZE WAS THE REAL PROBLEM: 945 prose blocks, 28,694 words, and 633 of the 945 over the
one-sentence budget. 255 ran to three sentences or more. The cause is a habit rather than an accident — nearly every note states a fact, then explains why it matters,
then names what would go wrong without it. Three sentences where a screen needs one, and the second and third are the DOCUMENT's argument rather than the
clerk's instruction. The budget, and the second line is what keeps it readable. A note, an alert or a hint keeps ONE sentence — except where it opens with a
bolded claim, which is a headline and not a sentence. Cutting "Print is the floor. Paperless and text reminders are channels on top of the paper…" to one sentence
leaves four words that tell a clerk nothing, so those keep the claim and the sentence that carries it. A stated absence keeps TWO, ruled: naming the gap AND what it
waits on is the whole point of one. ⚠  WHAT IS NOT CLAIMED. The removed sentences are not relocated one by one. They were elaboration, and this document
already argues at length in its captions, its section intros and this log — which is where a reader looks and a clerk never does. Saying they moved would be tidier and
would not be true.
THE STATE CHIPS BROUGHT BACK TO THEIR OWN VOCABULARY, AND SIX CHIPS THAT CLAIMED A COMMITMENT NOBODY HAD WRITTEN. Ruled: "you
should doble check whether these tags are corerctly applied on each anvery scren and section", then "Im okay with your recommendation - please fix it". Three labels were
outside the vocabulary. The rule is four state chips and only four — Exists behind, New read, New build, Blocked — plus No commitment where no specification covers
the screen. In use were also Second address twice, No story owns it once, and No screen, real data twice. Every one of the three was true and none of them was one
of the four, and a vocabulary with exceptions is one a reader has to learn twice. Second address becomes Exists behind — what makes it a second address is in its
routes line, where it reads as a fact rather than a state. No story owns it becomes No commitment, which is the word this document already has for that sentence. And
No screen, real data — mine — becomes two chips, New build and No commitment, because it was one invented label carrying two separate facts: the screen does not
exist, AND nobody has undertaken to build it. ⚠  SIX CHIPS CLAIMED A COMMITMENT THAT WAS NEVER WRITTEN. Ten cards exist, ACC-S1 to ACC-S10. Nine chips
cite an id and six cite S14, S15, S16, S17, S18 and S19 — none of which had a card. By this document's own rule, if a thing is not in a commitment card, nobody has
undertaken to build it — so those six were claiming an undertaking that did not exist. That is precisely the failure the rule was written to prevent, and the most
recent one was mine: I minted ACC-S19 for R9 and wrote no card for it. Two cards written, four ids withdrawn. R8 and R9 were both ruled explicitly, so each now
carries a real specification — what it waits on, the screens it changes, and what a person could do and see once it is done. R4 to R7 were not ruled, so their chips
come off and read No commitment: they are descriptions, and the document now says so. S14 to S17 are WITHDRAWN rather than reserved — they were never
issued, and a gap in a register suggests work somebody once undertook. And ACC-S19's card names the figure that makes it worth doing: one landlord in this
system holds three customer numbers, and a returning customer is asked for a second $150.00 deposit while the utility is already holding theirs. Seven cards that no
chip points at are NOT a defect — ACC-S3 and S5 to S10. A commitment may span screens that carry a state chip of their own, and every card already names its
screens. Said here so the asymmetry is not read as an oversight.
ONE TOOLKIT ABOVE EVERY TABLE A CLERK BROWSES, AND THREE RADIO GROUPS THAT WERE REALLY VALUE PICKERS. Ruled: "where you ahve use tables -
ensure you ahve toolkit above it ={ search bar, filter, colume silector, download button} - I see inconsistency at many plces", and on the radios, "im okay with these make
changes". ⚠  174 TABLES, 32 TOOLBARS, AND NOT ONE OF THE 32 CARRIED ALL FOUR CONTROLS. The download button did not exist on a single register in
the document — the only Export anywhere was on the Settings kinds screen, which had none of the other three. Thirteen toolbars had search, filter and columns; eight
had search and filter; three had search alone; one had filter and columns. 43 places changed: 26 toolbars completed, 17 added where a browse table had none. Every
one now reads the same way round — the filter beside the search on the left, the column selector and the export in the right group. The rule this applies, written
down so a later pass can check it rather than re-derive it: a table a clerk BROWSES carries the toolkit; a table that EXPLAINS does not. Ninety-three of the 174
are explainers — When / What, If / What you are told, Evidence / You typed / On file — and a download button above "What happens when you confirm" would be
worse than the inconsistency it cured. Twenty are pickers inside a wizard and keep their search alone: four controls over a two-row pick the account you mean is
furniture. Nineteen are fixed panels about one record. ⚠  ELEVEN OF THE FORTY-THREE ARE SUMMARY PANELS ON THE OVERVIEW TAB, NOT LISTS — three
recent bills, the services on the account, a usage strip. They are in because the count was quoted at 49 and approved at 49, and quietly delivering 32 would have been
worse than delivering something arguable. It is said here rather than buried: they come back off on one word. The radios: 46 buttons in 17 groups, and 14 groups
stay. The rule applied is that a radio earns its place when every option carries a consequence the clerk must read BEFORE choosing. A dropdown hides the
options behind a click, and hiding "$450.00 comes off the arrear and nothing is held if they come back" until after the choice is made is the wrong trade. Eleven groups
carry a sentence on every option; those are decisions, not values. Three convert, and each cures a real inconsistency. The transfer's person or company — customer
kind was already a dropdown on the new account, the move-in, complaints and services, and the transfer was the only screen drawing it as a radio. And
complaints step 3 and services step 3 ask the same question — does somebody have to attend — and drew it with four options on one screen and three on the
other. One list now, on both. ⚠  AND A DEFECT FIXED IN PASSING: the move-out's deposit step rendered a LONE RADIO. One live option, with the other three
refused elsewhere on the step. A single radio is not a choice, so all four are drawn with three disabled and carrying their reason — the rule the rest of the document
already follows. Which needed a class no stylesheet declared. .pw-radio.off did not exist, so the three disabled options would have rendered identically to the live
one while every structural check passed — an undeclared class is in the DOM and paints nothing. One rule added, beside the rules it extends.
R9 — THE CUSTOMER YOU ALREADY HAVE, FLAGGED ON ALL THREE DOORS THAT TAKE NEW CUSTOMER DETAILS. Ruled: "the system should flag if the details
were already attached to any of the accounts in the system and should show the details of the customer account with the proper customer details. This is very important
scenario." Then, on the first draft: "This same ... this looks like somebody you already have. This model should also be there in the move in Wizard and in the service request
capture." Five drawings. ⚠ THAT SECOND RULING CAUGHT A REAL MISTAKE, AND IT IS ONE THIS REPO HAS ALREADY WRITTEN DOWN ONCE. The first draft
capture.  Five drawings. ⚠  THAT SECOND RULING CAUGHT A REAL MISTAKE, AND IT IS ONE THIS REPO HAS ALREADY WRITTEN DOWN ONCE. The first draft
gave each host its own heading — "Two people are close, and neither is close enough", "We may already know this applicant" — each accurate on its own screen, and
together they made one feature read as three. That is exactly the lesson the field-visit panel records: one question, one panel, and the CONSEQUENCE sentence is
the part that varies. The title, the table and the evidence list are now emitted from one place and cannot drift, and a guard counts the title on all three hosts. And the
candidate is a DIALOG, not a page. A panel on three hosts would have meant three routes and three back-links; the dialog opens over the form the clerk is filling in
and closes back onto it with nothing lost. It is drawn twice — over the new account and over the service request — because the same dialog has to say something
different where the door creates nothing, and a single drawing would have hidden that. Its body is emitted once and a guard counts it twice. ⚠  ON THE SERVICE
REQUEST, Link to C-00412 IS GREYED WITH ITS REASON RATHER THAN REMOVED. Taking it away would make the dialog look like a different feature; leaving it
with "this door writes one request and creates no customer" on it says the opposite — same dialog, same customer, a door that cannot do that one thing. The verdict
column reads not judged there rather than borrowing weak, because a request form asks for neither a birthday nor a government identifier, so nobody has weighed
anything. Most of this is built, and what is missing is the screen — which changes the remedy from a matcher to a panel. The criteria were ruled on 2026-08-25,
verbatim "Name + date of birth + one government ID", the strictest of three readings, because refusing some genuine returners was preferred to handing a stranger
somebody else's deposit. One function resolves the party for four doors and answers in a single word — linked, created or none — and that word reaches no
screen: it is recorded in the audit row and dropped from the response. The cost is already on the register: one landlord holding three customer numbers. ⚠  AND A
PHONE OPENS AN ACCOUNT AND RECOGNISES NOBODY. A person is created on a Social Security number, a licence or a phone — and recognised only by the first
two. The move-in drawing is built on that case: a customer of four years stuck at weak because they were opened on a phone, beside a genuine stranger with the same
name. The useful answer is on the screen — ask for the licence and try again: one field, thirty seconds, and the deposit follows on its own. Money moves on a
strong match and nothing else, and nothing is preselected anywhere: the check is advice, the clerk decides, and a product that linked on its own would merge two
people's bills the first time it was wrong. Two more findings: probable is in the vocabulary and is never produced, and there is no way to undo a link. ⚠  ONE STALE
NOTE CORRECTED. The move-in review said "Linking at create is not built, so no prior history - and no prior deposit - can follow them in." That has been false since
2026-09-01. It now says the truer and more uncomfortable thing: the customer WAS resolved at save, a deposit CAN follow somebody in, and the clerk has no way to
see whether it just did.
§10'S CLOSE-OUT: ONE THIN DRAWING BECOMES THREE, AND THE DATE ON IT IS THE FINDING. Ruled: "there should be proper details on the close out. What will
happen after closing the account? and all. related to the closeouts." Why the act exists at all, verbatim and in full: "A disconnected customer can never be closed - Add a
separate close-out act — Cleaner in the record". The reasoning is part of the ruling — a close-out writes a date nobody can un-write, so letting a cut customer through
the move-out door would file a disconnection as a move-out in a permanent record, and to a regulator those are not the same event. The two doors refuse each
other in both directions, and the second half is the one a later lane will be tempted to delete: close-out refuses an OCCUPANT, because letting a departing tenant
through would file a departure as a disconnection — the same falsification pointing the other way. ⚠  THE CLOSING DATE IS THE CUT DATE, NOT THE DAY THE
CLERK PRESSED IT, AND THAT IS WORTH 43 DAYS OF AN EMPTY UNIT. A-11488 was cut 08/18/2026 and closed out 09/30/2026. Writing the later date would
make the next customer's earliest lawful start 10/01 — refusing a move-in on every one of the 43 days from 08/19 to 09/30, on a property the utility was entitled to
re-let the whole time. Writing the cut date makes it 08/19, which is exactly what the rules grant. Both dates are kept: the record reads service ended on the cut date,
and the account was closed out on this later day, by this person. That is what cleaner in the record means. Disconnected is not closed, and the screen now says so first.
A cut leaves the account OPEN — still owing, still able to pay, still able to be reconnected — and writes the final metered bill for the days before it ($23.23 of a $40.00
base, 18 days of 31). This door is the only thing in the product that makes such an account terminal. ⚠  AND THE OLD DRAWING SAID THE OPPOSITE. Its what this
screen is not telling you panel read "The final bill — Billing issues none yet", which a ruling of 2026-08-30 reversed: the cut raises the final bill. Corrected. What happens
after is now its own screen, because it is the question that was asked. The account becomes terminal and is never billed again; the unit is free from the day after
the cut; and the $612.75 survives untouched — closing an account is not writing off what it owes. A fresh collections case opens at tier 1 against the account itself,
as letters only: a closed account cannot be escalated to a disconnection, because there is nothing left to disconnect. And it is not tied back to a landlord — that
transfer is a clerk's deliberate act in the move-out wizard with a name recorded against it, and this door does not collect that consent, so it must not have that effect.
The third screen is the account a week later, which is where the disabled-with-a-reason rule earns its keep: five of the six header controls are off, each saying why on
hover rather than vanishing. Record payment stays live — a payment is always accepted whatever the status — and Reconnect is the one that changed at closing:
while the account was merely disconnected, paying the arrears and the fee would have brought the supply back; closing ends that, and the debt now follows the
person rather than the address. Three things this act does not do, named rather than implied. It writes no move record and no final-read state. It performs no
clearance — an active payment plan, an open dispute and an unbilled cycle are not looked up, and the screen is not telling you they are clear. And the reason is a
sentence somebody types with no list to pick from, so how many accounts did we close with a balance, and how much did we write off has no answer for any period.
One thing the customer gets, and it is the wrong one. Nothing announces the closure and there is no closing statement — neither template exists. The first thing
they hear is the tier-1 reminder asking for $612.75.
THE TWO FORMS BECOME PAGES WITH STEPPERS, THE SERVICE FORM GAINS A FEES STEP, AND THE REFERENCE DATA IS ONE SIMPLE SCREEN. Ruled: "A
complaint form should be of a staple form and on new page it should open up. Same for the services"; then "after the when and who, there should be also showing the
service fees … take them there. Or the service fees can be paid later … If paid later, it should be paid from the detail view showing that service fees are pending"; and mid-
draft, "the reference data for the services and complaints should be very simple. Just the user can add the kinds of services and kinds of complaints." Both dialogs are
gone. A complaint is /complaints/new, four steps. A service request is /services/new, five — who is asking, what they want, when and who, what it costs, review. Each
ends on a review that recaps every field from every step and carries the same communication section the other five wizards have. The fees step is drawn on a model
that already exists rather than a new one. A work order carries no price today, so this is a proposal — and not one invented from nothing: the service request's fee
model is ruled and built, so the step is that applied to a job. A line is a quote — a charge code, a basis, a quantity, an amount — and the amounts are this utility's own
codes, never typed. Collected is what the counter took. Outstanding is the difference, and it is a figure rather than a state anybody chooses: it is signed and never
clamped, so an overpayment reads −$15.00 instead of $0.00, because a customer who overpaid is owed money and flattening it to zero is how that gets kept.
Collecting refuses without a receipt and is idempotent on it — a clerk who presses again after a timeout does not charge twice. It raises no invoice and posts no
journal line: it is accepted and marked as cash, and finance reconciles it. And a line is waived, never removed — with a reason, against a name, and the line stays on
the quote at $0.00, so a customer who was not charged and one who was never quoted do not look the same six months later. Worked, across four drawings: $35.00
swap plus $15.00 delivery is $50.00 quoted; $15.00 taken at the counter on RCP-26-4902; $35.00 outstanding. That figure then follows the RECORD rather than the crew
— the job is booked and done regardless, because fees and field work are two queues on purpose — and it is on the Services tab as a KPI, in a Fees due filter, on the
job's own page, and behind a Take the $35.00 button whose consequences are drawn rather than named. ⚠  AND THE REFERENCE DATA WAS REDRAWN MID-
TURN, WHICH IS WORTH RECORDING. The first version was the whole work catalogue: nine headings, a tree, typed parent codes, three depth refusals, plus a second
screen for ranks, colours and SLA validation. Every word of it was true and none of it was what a utility opens this screen to do. What is here now is a narrow
door onto two headings — kinds of complaint, kinds of service, a name and a service to add one, rename and retire beside each row. The machinery still exists and is
still how it works; nobody has to meet it to add Water pressure complaint. A guard now refuses the screen if the parent codes, the ranks or the colours come back,
because re-adding them would undo a ruling quietly. Two things the simple screen still has to say. How fast is inherited unless it is set — eight hours for a complaint,
seventy-two for a service — and the four that are not (a gas leak, an odour report, no water, an outage) are marked, so nobody adds a fifth emergency and wonders
why it is answered tomorrow. And retire, never delete: a retired kind stays readable on every job filed under it, and the In use column is what stops somebody retiring
the one thing half the queue is filed under.
TWO MORE TABS ON THE REGISTER: COMPLAINTS, AND SERVICES — WITH THEIR TABLE, THEIR ADD FORM AND THEIR RECORD. Ruled: "in the main tab list,
add complaints and services. These two tabs. build their ad form and detail view. and tables." Six new drawings, and the register now carries ten tabs on every screen that
draws the strip. ⚠  NEITHER TAB EXISTS, AND EVERYTHING BEHIND BOTH DOES — that distinction is on the face of both sections rather than left to be
worked out. There is no complaints list, no complaint form and no complaint record anywhere in the front end. But a complaint is already a work order: Consumer
Complaint is one of the nine job types the Product Owner listed themselves on 2026-09-07 ("This are the work order types and subtypes"), it carries fifteen kinds beneath
it, and a job can already stand on an account — that is one of four anchors, with a database constraint stopping a job floating free of every record. What is missing is
the screen, not the record. So these six are drawn from the model that exists and invent nothing; where they show a gap, the gap is in the model and the drawing
says so. The two tabs are two types, and the difference is not cosmetic. Consumer Services is what a customer ASKED FOR; Consumer Complaint is what went
wrong. A container swap answered in three days is a good service and a missed collection answered in three days is not — which is why they carry different response
times, and why they are two tabs rather than one filter. Priority is a response time, and nobody types it. Urgent 4 hours, High 8, Normal 72, Low 168 — the due time
is stamped from the utility's own row the moment a job is raised. Every one of those hours is a per-tenant setting ("you keep them configurable in settings - user can
change the timings"), and the figures themselves are a lane's judgment rather than a signature, so no drawing here presents them as ratified. The form says the
eight hours are this utility's number, in those words. And four kinds beat their heading on purpose. A gas leak call-out, an odour report, no water at all and an
outage carry Urgent in their own right, because a sub-type with no default of its own inherits its parent's — so a gas leak hanging under a heading about consumer
complaints would quietly arrive with eight hours instead of four, chosen by nobody, with nothing on any screen showing that a choice had been skipped. The add
form says so where a clerk picks the kind. Four gaps the drawings surface, each read out of the model rather than imagined. (1) A job closes with a sentence
somebody typed and nothing else — no cause no outcome category no complaints register — so how many pressure complaints did we get and how many were
somebody typed and nothing else  no cause, no outcome category, no complaints register  so how many pressure complaints did we get and how many were
upheld has no answer in this product for any period, which is the first thing a regulator asks. (2) A complaint does not pause a collection ladder and the disconnect case
does not know it exists: the complaint drawn here is from a customer four days from being cut off, about the very bill being chased. (3) A job carries no price, so a
chargeable service is done and then billed by somebody remembering. (4) Nothing connects a container size to the plan that bills for it, so a customer swapping 96
gallons for 48 keeps paying the 96-gallon rate until a human changes the plan on another screen. ⚠  THREE SUB-TYPES EXIST UNDER CONSUMER SERVICES,
ACROSS ELEVEN SERVICES — a container swap, a water truck and a disconnect-or-reconnect. That is reported and not filled in: job types are a utility's own editable
list, and inventing seven more here would present this document's guesses as the product's. Both sections carry a No commitment row in so many words. They are
drawn because they were asked for and because the data supports them. That is not the same as somebody undertaking to build them, and this document keeps the
two apart.
§12'S DISCONNECT: FIVE STEPS DRAWN TO WHAT THE MODULE ACTUALLY HOLDS. Ruled: search and select with the customer's details and their financial details;
all the protections in detail, with decisions a clerk can take; the communication methods for the notice on the date step; all the applicable fees, collectable there; and a
review carrying every tab with communication options. The steps were checked against the code before anything was drawn this time — they are current, unlike
the transfer's. Step 1 carries the money, because that is why the ladder is running. The balance, the oldest item, the deposit, the last payment, the floor the ladder
needs to clear, and the three unpaid bills that reconcile to $2,410.00 exactly. Beside it, the reason — and the reason drives nothing: no fee, no notice period and no
protection changes because of it, and only non-payment has a lawful path to a cut at all, because a cut follows the final certified notice and the ladder that produces
one runs on debt. A meter found tampered with on a Monday never reaches that tier. Step 2 asks ten questions and only three have an answer. Medical certificate,
weather moratorium and active payment plan are answered by the product; a life-support registration, an age or disability protection, an open dispute, an assistance
application, a recent partial payment, whether the notice period was served and whether this is a landlord-billed premises are answered by nothing. They are drawn as
questions rather than hidden, because a screen showing only the three it can check reads as a clean check on a household nobody checked. The decisions are drawn
too — record one of the three protections with its own lifetime, or stop the ladder for one of three closed reasons — and then the step says the thing that matters:
none of it is operable on the shipped screen, which is handed nothing to write to and offers no control at all. Step 3 keeps the send and the proof apart, because
they are two different records. Six ways a notice goes out, of which certified mail is required at this tier and a text never stands alone; then the proof — the channel,
the receipt reference, the day somebody signed, and who recorded it. No proof, no cut. And the delivery column is left blank rather than filled in: nothing in this
product delivers a notice, and a made-up delivery state is exactly what a utility ends up showing a regulator when a customer says they were never told. The cut date is
computed and locked; later is allowed, earlier is refused twice. Step 4 shows all three fees and says which one is real. $75.00 reconnection, $45.00 disconnection,
$35.00 field visit — from the tenant's own charge codes, never typed. Only the reconnection fee is ever raised: the other two codes are declared in the module and
read by nothing, so a clerk quoting the designed table would say $155.00 and the customer would be billed $75.00. The fee lands at the cut and not at restoration,
which is the whole difference — charged at restoration, the arrears are paid, the balance reads zero, and the gate lets them back with the fee never collected. So
$2,485.00 reopens this supply, not $2,410.00. ⚠  And the cut refuses on this tenant today anyway: none of the three codes is in any catalogue here and the
reconnection one exists under no spelling at all, so every cut everywhere refuses until somebody adds the row. On collecting it there: the step takes a payment, with
the full figure prefilled and the three thresholds that matter drawn — clear it, pause the ladder, or merely record it. What it does not do is pretend that taking money
lifts the case: a payment is always accepted and accepting one changes no status, so somebody still has to stop the ladder on step 2 and say which of the three
reasons it was. The consequences panel now reverses two of its own sentences. It said a disconnected account keeps accruing base charges and that a cut does not
stop the balance growing. Both were overturned: a customer with no supply pays nothing for it, so after the cut the balance moves only when they pay, when a
correction posts, or when service returns. ⚠  AND NOTHING PERFORMS THE CUT ON THE DAY. No runner, job, queue or timer in this product reads a date and acts
on it. The scheduled date is stored and nothing watches it — a person opens the case and marks it cut. A utility that schedules and walks away finds the supply still on
and the fee never raised. It is on the review step, in those words. Two figures on the case record were wrong and are corrected. It quoted the reconnection fee as
$85.00 against a signed $75.00, and its consequence panel carried the exact billing sentence the base-charge ruling reversed. The review step carries every field from
all four steps and ends with the same communication section the other four wizards have — with one note of its own: queueing a letter is not serving a notice, and
the certified proof on step 3 is the only thing here a regulator would accept.
§11'S TRANSFER: REDRAWN TO THE JOB THE PRODUCT DOES, WHICH IS NOT THE JOB IT WAS DRAWN AS. Asked for: search and select with full customer
detail on step 1; a final read and read date on step 2; the unit details on the arriving step; the fees to collect on the money step; and a review carrying every field with
communication options. ⚠  THREE OF THOSE FIVE STEPS DO NOT EXIST, AND THE SUPERSESSION IS WRITTEN DOWN RATHER THAN ASSUMED. On 2026-09-
01 the Product Owner ruled, verbatim: "dont create new account - we reassing that account - bascailly I have sold my property - so account get transfer to new person or
business; if I move to new location then it is new Service request and we follow the process". A transfer is a SALE: one account changes hands. The number, the unit, the
meters, the plan and the whole ledger stay; the customer changes. There is no leaving, no arriving, no second address, no second date and no final read — the
commit door's own words are "a sale closes no account and opens none … the meter keeps running on one unbroken account". A customer MOVING is a new service
request, and that rule says out loud it has to be said on the screen where a clerk would otherwise reach for this wizard, so step 1 says it. Everything asked for that
survives the ruling is built, and the two that do not landed where the product actually puts them. Step 1 is the full search and select, with the account, the
customer, the unit, the meters, the plan and the cycle. The read ask landed on step 2's field visit: you do not type a reading on a sale, you raise the changeover read
as a job and the ordinary reads door serves it — that panel is already on this wizard today. The unit ask landed on step 3, read-only, as what is changing hands. And
the fees ask has an answer rather than a panel: a reassignment quotes nothing and collects nothing — no journal line, no refund, no invoice, and neither the balance
nor the deposit is touched — so the step states that there is no change-of-ownership fee in this product and names what defining one would need, instead of drawing
a payment form that would post nowhere. The money step has no switches any more, and that is the ruling. It used to ask whether the deposit carries and whether
the arrears follow; both were answered the same day — "money follow property - new owner boutght everything property + debt also" — so a box for a clerk to clear
would be a control that can reverse a ruling. What is left is the figure, shown: $318.40 and a $150.00 deposit, taken on by the buyer. ⚠  AND THE SHIPPED WIZARD
CANNOT COMPLETE A TRANSFER AT ALL. The running screen is still the five old steps, so it posts a destination unit, two dates and two elections that the commit
does not read — and never sends the buyer, which the commit requires. Every attempt refuses at the second of five writes, with a message about a field that
appears on none of the five screens. Nothing catches it: the wizard's own tests assert the old steps and pass. The list and the record were rebuilt too, because they
still described two accounts, two dates and a deposit being carried. They now show one account, one date and what the buyer took on. Two things the record says
are still wrong afterwards, deliberately: a sale does not rewrite the property's owner record, and the account keeps the seller's email, paperless election and autopay
instruction — so unless somebody changes them, the buyer's first bill is emailed to the seller and may be paid from the seller's bank. The review step carries every
field from all four steps and ends with the same communication section the other three wizards got, with one note of its own about which address these letters would
actually reach.
§08'S MOVE-OUT: SIX STEPS BECOME FIVE, AND THE MONEY IS DRAWN AS THE ONE SUBTRACTION IT IS. Ruled: search and select on step 1 with the account
and unit in full; a move-out date, a final read AND its read date, or an estimate; the deposit's available actions on the final-bill step "and the shortfall should be part of
the final bill and deposit"; everything important on what happens next; and a review carrying every field. ⚠  AND THE SUPERSESSION THAT PASS RECORDED IS
WITHDRAWN, WITHIN THE TURN. Folding the shortfall into the final bill would have superseded BR-SHL-046 — PO, verbatim "6 steps", closing DEF-648 — so it was
written down as one, precisely so it could be found again. It was reversed on the next instruction: the shortfall is its own step and BR-SHL-046 stands, unamended. The
note is withdrawn rather than left to confuse the next reader about which way this went — which is the whole reason for writing a supersession down instead of just
making it. How the money lands is not a choice, and the step now says so. It is one subtraction — prior balance plus the net final bill, less the deposit, its interest
and any unapplied credit — and the answer decides the case: above zero is short, zero is settled, below zero is a refund unless a dispute holds it or a sibling account
owes us money. The prototype's five-way switch is deliberately not built: "this is only for reference not for design". All five landings are shown, with this account's
marked. ⚠  AND THE SCREEN CANNOT REACH THE SIGNED FIGURE. The frozen pair applies $153.50 — a $150.00 deposit held fourteen months at 2% simple earns
$3.50 — and deposit interest is not tracked, so applied counts the deposit alone. The consequence runs against the customer: a smaller amount applied makes the
shortfall bigger, so the account is asked for more than the signed arithmetic says it owes. It renders as not recorded, never $0.00, because zero would be a claim. The
deposit's four actions are drawn with the three that do not apply saying why — a refund needs the subtraction to land below zero, holding needs an open
dispute, and transferring is a different flow. The four shortfall paths are collect, a payment plan, transfer, or write-off, and a transfer's target is resolved by the server
rather than typed. ⚠  AND IT RECONCILES ONE STORY ACROSS FOUR DRAWINGS. 1408 Elm · Unit A: A-10432 (Okafor, D.) moves out 01/28/2026, the unit is vacant
from 01/29 for 94 days, and A-12051 (Miller, Sarah) moves in 05/02/2026. Section 08 had the wrong occupant and three different move-out dates across the wizard, its
list row and its record.
THE DEPOSIT BECOMES OPERABLE, AND THE SHORTFALL GETS ITS STEP BACK. Ruled: "What can be done with the deposit is given. but there are no actions that
can be done on the deposit … After the final bill and deposit step, move the short fall step after that." The complaint was right. The last pass drew a TABLE of what can
be done with a deposit — four rows, a yes-or-no column and a reason. It described the options accurately and offered none of them: a clerk reading it could not apply,
refund, hold or transfer anything. It is four CONTROLS now, and the one this account can use carries the fields it needs — an amount to apply and the date it applies
on. Which of the four is available is decided by the subtraction, not by the clerk. Apply is the only live option while the account lands short; a refund needs the
subtraction below zero, holding needs an open dispute, and transferring is the transfer flow. The three render DISABLED WITH THEIR REASON rather than vanishing,
and a panel names what each would ask for so a reader can see what a refund needs without hunting for an account in the right state to make it appear The
and a panel names what each would ask for — so a reader can see what a refund needs without hunting for an account in the right state to make it appear. The
shortfall is its own step again, with all four paths as controls and a table of what each asks for and who may do it. Collect it is the default on purpose: it is the only
one of the four that changes nothing about whose debt this is. Moving it to a landlord, forgiving it, or rescheduling it are deliberate acts — and the transfer especially,
because it points the reminder ladder at a company that has never heard of the tenant.
A COMMUNICATION SECTION ON THREE WIZARDS' FINAL STEPS. Ruled: "there should be some communication section where the user should select what type of
communication should go to the customer" — on the new account's review, the move-in's review, and the request capture's check-and-submit. All three already
ENDED with a stub about messages — a Welcome / not sent pair on the move-in, an Acknowledgement note on the request, and nothing at all on the new account.
Each is now a section a clerk operates: what goes out, to whom, on which channel, from which template, and when — with a template search beside it. Three rules
shape them rather than decorating them. Everything is QUEUED and nothing is sent: this product writes a row per message and no sender picks it up, so a screen
saying sent would claim something nobody did. PRINT IS THE FLOOR — paperless and text are channels on top of the paper, so an account that elected paperless gets
the email AND the envelope. And a template resolves on three axes, falling back to the default variant for a category or a language, so picking one does not leave every
other case unhandled. A draft version is listed and cannot be picked: hiding it sends a clerk looking for something they can see exists, and offering it would queue a
letter nobody approved. Each section's unticked rows are the useful part. On the move-in, the row nobody can send is that a meter still has to be read — one
register opened unread and could not be estimated, so the account starts with no demand figure and the customer has not been told; it is unticked because no
template exists for it, which is a gap rather than a choice. On the request, the ticked documents outstanding row is the difference between an application that moves
next week and one that sits — and the counter receipt records what was already handed over rather than queueing a second copy.
EVERY TAB AND EVERY ACTION ON THE ACCOUNT, DRAWN — 27 NEW WINDOWS. Asked for directly: "build each and every tabs wireframe in the accounts detail
section. Don't miss anything from the account. Also build every actions wireframe." Twelve tab drawings (ACC-T01–T12) and fifteen action drawings (ACC-A01–A15,
Change plan taking three because it has three steps). The document goes from 61 drawings to 99.
ALL OF SCREEN 02 IS NOW ONE ACCOUNT: A-11812, BRAMBLE BAKERY. Ruled after the first cut drew the new tabs and actions on a different customer from the
as-built drawing above them, so one screen carried two names. Every drawing in screen 02 and in R4 was re-read off Bramble Bakery on 2026-09-11 and redrawn —
figures, columns and sentences, none of it relabelled from the other account.
It turned out to be the better account, and not by a little. A small commercial customer in collections: $2,410.00 outstanding, 62 days past due, two dunning
notices issued and disconnect case DSC-26-0003 already open — and not one bill ever issued, the balance carried in as an opening figure. Two services open since
September 2024 against a unit with no meter, so nothing has ever been measured. One payment, $500.00, sitting in Processing because it was entered with no clearing
date. Seven of the thirteen actions refuse on it rather than one, because three rail icons need an issued bill — which makes it the clearest picture in the document of
how much of this screen goes dark when billing has not run.
Four findings the walk produced that no earlier pass had. (1) Activate account has no confirmation — one click commits, and it then reports two things the
server could not do on an account it has already moved to Active. (2) Issue credit drops the account where it is live, landing on Billing › Fix a bill with an empty bill
box. (3) Close out has no reachable state: disabled on all four seeded statuses, and the one status it exists for has no account at all. (4) Change plan renders no step
rail; its three step numbers live in the headings, so a clerk cannot see how many steps are left.
THREE PLACES IN THE PRODUCT PUT INTERNAL STRINGS IN FRONT OF A CLERK, all on this one account, and B14 rule 32 forbids every one. The Overview tab
prints the sub-type as small_commercial. Change plan step 2 shows BR-CUS-042, OQ-179, BR-RAT-004, OQ-180, the Python path apps.rating.engine.prorate_base_charge and
the columns deposit_differential and usage. And the Audit tab is the worst: three events all reading this event type is not described yet, one of them opening onto
sixteen database field names — tier_1_reminder, tier_2_10_day, notice_sent, DSC-26-0003 — nine of them empty. What actually happened is a reminder, then a ten-day
notice, then a disconnect case. The words are on the screen; the sentences are not.
A commercial account is on a residential plan, because the plan follows the unit and the account's category is its own fact. Nothing reconciles the two and no screen
warns that they disagree.
Two faults in this document's own v14 base were corrected on the way. The old two-modal block captioned Record payment and Add note as one flow committing
to both POST /accounts/{id}/payments and POST /accounts/{id}/notes. They are two independent modals: neither carries a stepper and neither mentions the other.
Separately, the fit script paired two-up on indexOf("pw-f") === 0, which also matches pw-fact, so read-only label/value rows were being laid out as form fields.
WHAT THE WALK COST, SAID PLAINLY. Reading Activate account on A-12048 activated it: the button commits on click with no confirmation, which is the finding,
and the account is now Active. It was the deployment's only pending activation account, and restoring it was refused, so the earlier reproduction of "Close out is live
on a draft account" can no longer be re-run on this stack. The gate that causes it is still readable in AccountDetailPage.tsx — the close-out test is !(occupying ||
closed), which lets pending activation through — and that code, not the walk, is the durable evidence. The $500.00 payment on Bramble Bakery is also this document's:
entered on 09/11/2026 to test what a missing clearing date does. It is drawn as what it is. Nothing else in the walk wrote to the product.
SCREEN 02 REDESIGNED AGAINST THE PRODUCT, AND ITS RULES WRITTEN UNDER IT. Seven named groups (Money · Service · History · Customer · Billing
preferences · Account setup · Portal access), all six actions and all seven rail icons kept on screen and disabled with their reason per the PO's ruling, and eleven served
fields that were drawn nowhere now on the page — ageing first. Two truth tables under the drawing record what is live in each of the six account statuses, every cell
read off the running product one account at a time.
The document was breaking B14 rule 32 and the product was not. Nine rule ids sat inside drawn screens; five live screens were searched and carry none. All nine
rewritten into a clerk's language. A re-scan of all 61 drawings returns zero. The one internal string the product really does show — the raw sub-type enum — is drawn
as it is and filed as a finding.
Three header changes, each with a reason. The service address is now an icon carrying its own accessible name, which frees a text label the header needed; the plan
tile shows the code with the full name on hover, because the code is what a clerk quotes; and Customer ID and Linked accounts replace the empty usage-trend note,
which said nothing a clerk could act on.
SCREEN 02 REDRAWN TO THE PRODUCT'S INFORMATION ARCHITECTURE, AND THE OLD DRAWING HAD BOTH THE ORDER AND THE CONTENT WRONG.
Reported from a production screen: "my screen layout from product is better - can you match it". The product renders kicker + actions on ONE row, then the status pill,
the address, the service chips, then the tabs, then the KPI band, then the rail. The drawing had the band first, gave the rail text labels it does not have (it is seven icons
and nothing else), and put the tabs last. My own walk data already said so — the captured DOM order was in this session's notes and I drew it wrong anyway.
And it was short by nine blocks. The Overview tab carries eleven and the drawing had two. Now drawn: Recent bills · Usage trend with its chart, its "9 month(s) have
no reading" footnote and the twelve-month stat row · Account · All accounts for this customer · Customer with its mailing address and note · Payment method · Deposit
& credit · Portal access · the ACC-02 badge. Every refusal sentence is kept verbatim, because §08 is built from them.
A class-name collision between the report and the drawings, and it is the single cause of four overlapping elements. This document owns .v — an inline health
badge carrying white-space:nowrap. The drawings use .v too, for a KPI value and a fact value. .pw-kpi .v wins only the properties it sets, and it never sets white-space —
so the badge's nowrap applied to every value in every drawing and a 30px KPI value painted 135px across its neighbouring tile. ⚠  Nothing caught it, and the
reason generalises: every check here asks whether a DRAWING fits its BOX. drawings=61 · clipped=0 · scrollX=0 were all true and all green over a tile printing on top
of another tile. A collision probe — does any child paint outside its own cell — now runs alongside, and it is what found the other three.
THE APP WAS BOOTED AND DRIVEN, AND THE REASON THIS DOCUMENT GAVE FOR NOT DOING SO WAS MOSTLY WRONG. The previous version put 0 of 14
journeys walked on the masthead and listed five blockers. Four did not survive one command each: PostgreSQL 16 was installed all along, pip was present, node_modules
is gitignored so npm ci touches nothing tracked, and Docker was never required. I let the "analysis only, no repository writes" instruction do work it was never
asked to do — it forbids writing to the repo, and it says nothing about whether a database may be started in /var/lib. The stack now runs on a real PostgreSQL with
334 migrations and 1,647 seeded rows, and git status --porcelain is still empty.
One real defect, found only by driving it. Two API paths in this module are built without a leading slash, so they weld onto the tenant segment and 404:
closeOutEndpoints.ts:131 (the close-out preview and its commit) and MoveOutWizard.tsx:1166 (move-out's settlement read). Proved both ways against the running server
— §07. Every other API path in 07-frontend/src starts with a slash; these two are the only exceptions in the tree.
Every drawing is now one desktop window, and it fits its box. The drawings used to be fluid: they took the reading column's width, reflowed inside it, and needed
an internal scroller — so the shell read as a squeezed product rather than the product. Each is now a fixed 1440-wide window at the product's own literal sizes, scaled
as a unit to the width available. Verified in Chromium at twelve viewport widths: 0 drawings clipped, 0 pushing the page sideways. ⚠  The first attempt failed the
same test it was written for — centring on left:50% with 100vw put every drawing 135px off-centre and gave the page 107px of horizontal scroll, because 100vw
includes the scrollbar and a percentage cannot see it. It measures clientWidth now.
The drawn shell was missing a nav item, on all 61 drawings. Measured against the running product: the sidebar is 240px with thirteen items and the drawings had
twelve — Reports was absent everywhere. Also corrected from measurement: the tenant block is a BB square plus Brazos Bend Utilities (the drawings said "Brazos Bend
Water & Light"), the topbar is 56px, and the page title is 40px, not the 32px --text-h2 the stylesheet's default implied.
Four of ten steppers disagreed with the screen. Six wizards were opened in the running app and their rails read. New connect (9 steps), Transfer (5), Disconnect (5)
and Import (5) matched exactly. New account, Move-in, Move-out and Service request had ten wrong labels between them — Unit for Service address, Settle the
money for Final bill & deposit, and so on. All corrected to what the product renders.
The accounts list is drawn from real data now It showed r10's illustrative 1 247 accounts and $184 320 It shows the seeded tenant's 72 and $24 992 65 the two
The accounts list is drawn from real data now. It showed r10 s illustrative 1,247 accounts and $184,320. It shows the seeded tenant s 72 and $24,992.65, the two
uncounted tiles in the product's own words ("Not counted yet", not "Awaiting"), the real pager, the icon-only Columns control, and three rows that exist. No kicker,
because the live list has none.
One spacing scale, measured rather than chosen. The drawings had drifted onto ad-hoc values — 3, 5, 7, 9, 10, 14px — so components read as touching and a field's
helper text sat as close to the next field's label as to its own input. Seven steps taken from the product by getComputedStyle: 4 · 8 · 12 · 16 · 20 · 24 · 32. The field rhythm
is a ratio, not a number — label 5, helper 6, next field 20 — so the helper text belongs unmistakably to the input above it.
Fields pair two to a row where two fit. 187 fields across 60 groups, 40 of them rendering two-up at desktop and folding to one inside the narrow column, from a
single rule with nothing set per screen. A field holding a textarea keeps the full width.
A self-caught probe error, recorded rather than quietly fixed. My first search test reported the accounts search dead. It was not: my selector had filled the topbar's
global search, because the page has two input[type=search] elements. The accounts search is server-side and correct — ?q= reaches the handler and an address
fragment matches. The finding was mine, not the product's.
A PO ruling that is in this document and NOT in the repository. The default sort should be creation order, newest first — quoted verbatim in ACC-S11. Hard-won
law 9 wants it in the decision log the turn it was made, and the no-repository-writes constraint means it is not there. Until it is, the next agent will not find it.
The read was pinned, and then it moved. The audit was taken at 2824c2e5 / 2.234.15. Between starting and finishing, the repository's default branch advanced 19
commits to 857f3abf / 2.234.16. That was checked, not assumed: none of the 63 changed files is in the Accounts surface, and the two shared components that moved
gained optional props that are absent by default.
Every route carries the tenant segment. Routes are mounted under path: `/:${TENANT_PARAM}`, so all 17 addresses in this document read /:tenant/…. Getting that
wrong once would have made every address in the document wrong.
Seventeen routes audited for doors; none was left NOT NAMED. The count on the masthead is 0 of 17, and it is the answer this process most often reports as a
failure. Here it is a pass, and saying so plainly is more useful than manufacturing alarm.
One finding struck and answered rather than deleted — the icon rail. This audit's own first pass repeated AccountIconRail.tsx's docstring (three live, four dead).
Reading accountRailReadiness.ts showed six of seven reachable. The original claim is struck in §08 with the correction beneath it.
Two of my own errors are named in the appendix rather than quietly fixed: a substring grep that misreported the Tailwind migration status of the two main screens,
and a guessed locale-key search that produced a false "missing key" finding. Both are recorded because they tell the next reader which checks are fragile.
A structural fault is reported and deliberately not repaired. The close-out screen has no screen ID and no epic. This document gives it entry 10 for navigation and
leaves the gap visible, with ACC-S7 naming it — rather than assigning it an S-number, which would silently assert that one was allocated.
Counts were recomputed from the finished markup, not accumulated by hand, and two were wrong on the first pass: cross-module facts read 26 and are 13;
specifications read 7 and are 10. Both are corrected above.
The phone drawings were cut, on the product owner's instruction, and every drawing is now the desktop screen at 1280. Sixteen wireframes were removed. The
prose that claimed both widths is corrected rather than left standing, and the loss is recorded in "what was deliberately left out" below — a document that drops half
its evidence and goes on describing itself as complete is the failure this section exists to prevent.
The wireframes were drawn in an invented style and are now the LIVE UI. Reported by the product owner: "the UI wireframes are not as per the current UI that we
have live." True — the first pass drew a generic wireframe kit: a blue accent, rounded corners, boxed KPI cards, a circle-and-line stepper, a light nav rail. Every one of
those is wrong. Read from the repository and corrected: the palette is tokens.css (#ec3013 accent, #f3f2f2 ground, #eae9e9 surface, #201e1d ink), the typeface is
Archivo at weight 800, and every radius is 0 — that file's own words are "Modernist is square; keep 0, do not fix". The sidebar is an inverted ink panel with an accent
square on the brand and an accent fill on the active module. The KPI strip is a band with 2px rules and vertical dividers, not cards. The wizard rail is a full-width band
with square badges. Buttons come from buttonKit.ts — primary is solid accent, danger is outlined. Pills, inputs and the data table carry their real geometry.
The nav was drawn wrong and is corrected. Screens 01 and 02 drew the module nav as a TOP row. SHELL_NAV is a side rail (AppShell.tsx:216, rendered :752), and the
product has never had a top nav. Reported by the product owner off the published page; all 61 wireframes now carry the side rail, and the two hand-drawn screens
were rebuilt on the same shell as the generated ones so they cannot drift again.
Every step of every flow is now drawn as a full production screen. The first pass drew one representative step per wizard — step 5 of the nine-step new connect,
step 3 of the six-step move-out — and listed the rest in prose. That is a ninth of the new connect audited and shown as if it were the whole. The document now carries
58 frames: all 56 flow steps plus the two list/detail screens. The step data is generated from the same source as the companion Accounts Surface page, so the two
cannot drift about what a step contains.
Nothing else was deleted. Every finding, including the ones that turned out to be wrong, is present — struck, corrected, or named as an error.
14
Appendix — the whole document, compressed
A · Every rule this document states
Rule As stated Where Home
UI-RULES 7 Every date uses .date-input with a Today shortcut §09 INHERITED  r10 / B14
UI-RULES 11 · 14 · 16 · 17 · 19 Consequence preview · column selector · pagination · empty state ·
search placeholders
§01 · §09 INHERITED
B14 rule 21 New UI is Tailwind — but only in a file on route-b-migrated.txt §01 · §10 INHERITED
BR-SHL-025 · 044 Disabled with a reason · one header, one primary §01 INHERITED
NFR-3 · NFR-5 Universal server pagination · no hard caps §01 · §02 INHERITED
Hard rule 4 Financial immutability — so an edit control on a payment or an
issued invoice is a finding, not a feature
§01 INHERITED
A list states the scope of its
sort
A footer says whether the ordering covers the whole result set or
only the page
§10 · R2
⑨
NO HOME
A hold carries a test that fires
when it expires
A refusal written with a clock in it gets a test that fails when the
clock runs out, in the same commit
§12 ·
ACC-S6
EXTENDS  hard-won law 2, which states the hazard but prescribes the
test only for dead UI, not for a rotting refusal
Two NO HOME / EXTENDS rules. A rule stated only in a document nobody
reads is a rule that is about to be broken — both are in commitment cards for
exactly that reason.
B · Every worked figure, numbers intact
None of these is a signed figure. Every drawing in this document is an
illustration and every number in it is a test case, unverified. The rules that would
govern them if they were real are B4's money maths (4 decimals stored, 2
displayed, half-up) and B4.3's calendar-day proration — a verifier checks against
those, not against this table.
Figure Where The surrounding sentence Status
A-10432 · Miller, Sarah 01 · 02 · 03 · 04 ·
08 · 13
The account followed through the whole flow Illustration
$247 30 01 02 08 Balance prior balance at move out Unverified
$247.30 01 · 02 · 08 Balance · prior balance at move-out Unverified
$150.00 02 · 08 · 11 Deposit on file · held principal at transfer Unverified
$612.75 01 · 10 · 14 A-11488's outstanding balance · the balance a payment
plan spreads
Unverified
$112.75 down · 5 × $100.00 14 (612.75 − 112.75) ÷ 5 = 100.00 exactly, so no remainder
lands on the final row here
Unverified — and deliberately a clean division, so the remainder rule is
stated rather than demonstrated
$30.50 → $42.00 · +$11.50/mo 13 Change-plan preview: current base, new base, net impact Unverified
1,247 accounts · $184,320
outstanding
01 KPI strip — r10's own figures, carried forward Illustration
40,000 02 · R2 T5's ceiling, used to size the NFR-3 finding From CLAUDE.md, not invented
562 ms for 73 accounts 02 The NFR-3 finding's only measured datum Real — recorded in the DEF-2723 comment in selectors.py
M-4021 · M-4022 · 48,209 · 1,204 ·
51,776 · 1,388
02 · 04 · 08 Meter numbers and opening/final reads Illustration
1,904 will load · 62 warned · 34
blocked of 2,000
15 Import dry run — sums to 2,000 Illustration, arithmetic checked
C · Every screen, with its exact contents
# Route Tabs Table controls Write surfaces How you get here
01 /:tenant/accounts 8, in URL search SERVER · 6 filters SQL + 2 in memory · columns
persisted · sort in memory
detail ✓  · add ✓  · edit NOTHING · update
NOTHING
It is the door + 5
more
02 /:tenant/accounts/:accountId 12, in URL n/a — embeds billing's and payments' own detail n/a · add ✓  (note, payment) · edit
NOTHING · update NOTHING
33 doors
03 /:tenant/accounts/new None · 6 steps n/a add ✓  POST /accounts 3 doors
04 …/:accountId/move-in None · 5 steps n/a add ✓ 2 doors
05 /:tenant/move-ins/new second address
of 04
n/a add ✓ 4 doors
06 /:tenant/requests/new None · 6 steps n/a add ✓ 5 doors
07 /:tenant/connections/new None · 9 steps n/a add ✓  (bulk) 3 doors
08 …/:accountId/move-out None · 6 steps n/a update ✓ 1 door
09 /:tenant/move-outs/new second address
of 08
n/a update ✓ 4 doors
10 …/:accountId/close-out None · 1 page n/a update ✓  (danger) 1 door
11 /:tenant/transfers/new None 5 steps n/a add + update ✓ (one transaction) 3 doors
11 /:tenant/transfers/new None · 5 steps n/a add + update ✓  (one transaction) 3 doors
12 /:tenant/disconnects/new None · 5 steps n/a add ✓  (danger) 4 doors
13 …/:accountId/change-plan None · 3 steps n/a update ✓ 1 door
14 …/:accountId/payment-plan None · 3 steps n/a add ✓ 1 door
15 /:tenant/accounts/import None · 5 stages n/a add ✓  (bulk) · rollback ✓ 2 doors
16 /:tenant/requests None its own, suppressed when embedded detail ✓  via 👁  only — the number is plain text 4 doors + the tab
embed
17 /:tenant/requests/:requestId None n/a update ✓  · delete refused by rule — a fee is
waived, not deleted
3 doors
D · Decisions recorded here and nowhere else
D1 — rules that live only in this document: the two NO HOME / EXTENDS rows in table A. Nothing else.
D2 — rulings already recorded elsewhere · do not re-ask:
Ruling Where it lives
Search prompts may read a bare field list where the sentence is server-served — OQ-600, open 14-ui-conventions.md:205-211
The seven rail glyphs and their order — "Seven icons, label appears on hover" BR-SHL-045, PO 2026-08-24
Autopay is capture-only in v1 BR-CUS-059
Move-out is six steps, not four — "6 steps" BR-SHL-046, closing DEF-648
Close-out is a separate act from move-out DEF-724, PO 2026-08-27
The customer-number column leaves the list but stays searchable — "on account tab - we dont need this column" PO 2026-08-24
The "4 accounts" sub-link is cut — "okay dont link it" PO 2026-08-24
A search technique that gave a false negative, recorded because the next
person will hit it: en.json is flat, not nested — keys are literal dotted strings. A
nested-dict lookup returns None for every key and looks exactly like "the key is
missing".
E · Every guarantee, and what enforces it
Only a constraint refuses. A convention is a habit with a good reason, and a
habit does not stop a caller.
Guarantee What enforces it Refuses?
One active account per unit Service-layer check + 409 on move-in SERVICE RULE  yes
Tenant isolation PostgreSQL RLS with FORCE DATABASE CONSTRAINT  yes
An account's unit and type never change update_account skips them by name SERVICE RULE  yes
A terminal status is reached by a flow,
never an edit
_apply_status_change SERVICE RULE  yes
Money carries its currency Decimal string + CHAR(3) travel together CONVENTION  no — nothing stops a caller separating them
A disabled control states its reason RowAction makes the reason a required prop — forgetting it does
not compile
SERVICE RULE  yes, at the type level
Every UI rule in B14 Nothing reads rendered output CONVENTION  no — which is why §09 exists
A Tailwind utility renders route-b-migrated.txt + the compiler CONVENTION  no — a utility in an unmigrated file renders as nothing and
every check passes
F · What this document assumes and never says
Assumption Where it hides What breaks if it is wrong
A link that exists lands where it says Every "how you get
here" row
Checked for the account row, which lands on the detail screen. The other 32 inbound links are still read, not clicked
The demo figures resemble real tenant
data
Every wireframe Layout only. The numbers are test cases and say so
Line numbers stay put Every path:line
citation
Citations drift with the next commit; the file and symbol names are the durable half
Reading the source tells you what the
code does
The whole document Nothing catches a control that throws only at runtime. This is the expensive one
That the 19 commits I did not read
change nothing here
The masthead Checked by filename, not by reading all 63 files. If one of them touched an Accounts path under a name I did not match, a
statement here is stale. The most expensive assumption in this document
G · Every UI rule violation
One row. See §09 for the full statement — screens 03 · 04 · 08 · 10 · 11 · 12 · 13 ·
14, UI-RULES 7, no .date-input exists in the codebase, RATIFIED, UNENFORCED .
H · Every cross-module finding
From To The handoff or shared fact What is wrong What breaks
customers billing The final-bill handoff
assembled at move-out
It is returned and stored nowhere — no table, queue or outbox Billing is the intended reader and cannot read it; the record
lives in one HTTP response and an audit row
p
customers metering An interruption raised from a
service request
A direct import with no declared seam causes
Interruption.objects.create()
Nothing today — metering's own service runs its rules. The
boundary is the problem, not the row
customers billing The ageing vocabulary Two homes. ageing_segment (4 bands, served) sits beside aging
(3 states, null) on every row
When billing publishes its version, two vocabularies describe
one fact. That is a ruling, not a merge
customers metering STORABLE_KINDS and the service
catalogue
Reads across the boundary bypassing a seam Nothing today; the coupling is invisible to either module's
tests
Question 4 — does the same thing have two names? — found nothing in
this flow, and that is stated rather than left to be inferred from an absent
heading.
I · Every field, and where its data comes from
17 of 30 traced fields are SERVED. 15 of 17 screens were not field-traced at
all — screens 03–17 carry the rows that discriminate rather than a field table
each, which is this document's largest deliberate omission. An untraced field is
not a healthy one, and it is not counted as one. Sorted by source so every
consumer of one column is on adjacent rows.
Source Screens Endpoint Owned by Health
accounts.account_no 01 · 02 GET /accounts, /accounts/{id} customers SERVED
accounts.closed_at 01 (KPI) — customers NOT SERVED  no date filter exists
accounts.credit_tier 02 GET /accounts/{id} customers
 STUBBED  always null
accounts.custom_data 02 GET /accounts/{id} customers ⇄
tenancy
SERVED
accounts.deposit_on_file 02 · 08 · 11 · 12 GET /accounts/{id} customers SERVED
account_opening_buckets 01 GET /accounts customers SERVED
account_plan_assignments 02 · 03 — no DDL in any signed document customers NOT SERVED
contacts.full_name 01 · 02 GET /accounts customers SERVED
contacts.gov_id_last4 02 · 06 GET /accounts/{id} customers SERVED  masked
premises.address_line1 01 · 02 GET /accounts customers ⇄
metering
SERVED
ledger journal lines 01 · 02 · 14 GET /accounts (via _ar_positions_for) customers ⇄
ledger
SERVED
billing invoices 01 · 02 GET /invoices?f.account_id= customers ⇄
billing
SERVED
billing
billing — open-invoice due dates 01 (KPI) · 02 (due
date)
— no module publishes it per account billing NOT SERVED
assets registry + reads 02 GET /assets/{id}, /assets/{id}/reads — one
per meter
customers ⇄ assets SERVED
portal_credentials + portal_sessions 02 GET /accounts/{id} via portal_seam customers ⇄ portal SERVED
rating — unit plan in force 02 GET /accounts/{id} unit_plan customers ⇄ rating DERIVED  the unit's, shown where the
account's belongs
a literal badge map in ratingShared.tsx 01 · 02 — — HARDCODED  the eleventh-service hazard
ACCOUNT_SEED_STATUSES in
customersShared.tsx:166
01 — — HARDCODED  a tenant-added status cannot
be filtered
deposit interest 02 · 08 · 11 — no column exists — NOT SERVED
account documents 02 — no table, no endpoint customers NOT SERVED
adjustments 02 — no endpoint billing NOT SERVED
J · Health, and what the grade rests on
A screen's health is the worst of its fields, never an average. An average
turns one broken field among nine good ones into "90% healthy", and the
screen still does not work.
J1 · Fields
Verdict Count
SERVED 17
DERIVED 3
HARDCODED 3
STUBBED 1
DEAD 1
NOT SERVED 5
Not traced at all screens 03–17, all fields
J2 · Flows
Screen Verdict
01 Accounts list BREAKS AT billing  — last bill and the past-due tile both need an AR position no module publishes per account
02 Account detail FORKED  — the plan is read from the unit because the account's own snapshot has no table, and the ageing vocabulary has two homes
03–17
 UNVERIFIED  — not walked, and not field-traced. Not graded WHOLE on a read
J3 · Seams
From → to File Verdict
customers → portal portal_seam.py:85 HEALTHY
customers → tenancy lookups.py HEALTHY
customers → ledger import_writer.py HEALTHY, NO SEAM FILE
customers → metering service_request_api.py:907 LEAKY · writes by effect
customers → metering service_request_service.py LEAKY
customers → metering + tenancy sample_data.py
 NOT GRADED  — fixture code, listed so six is honest
Completeness, scoped
This document is exhaustive over itself — every rule it states, every figure it prints, every screen it draws, every decision it records, every guarantee it sorts, every assumption it
names. It is not exhaustive over the product, which has behaviour these seventeen routes never touch.
And it is as stale as the read it was made from: version 2.234.15, commit 2824c2e5, 2026-09-10 — with the default branch already 19 commits past it at 857f3abf / 2.234.16.
What was deliberately left out, and why
Every phone drawing. Cut on the product owner's instruction; all 17 screens are drawn at desktop 1280 only. What goes with them is the width where ordering decisions become
visible — which of the five KPI tiles survives first, whether the seven-glyph rail wraps or scrolls, what an eight-column table does at 390. Two of these flows (move-out and
disconnect) are run standing up, so that gap has a cost even though the register itself is a desk screen.
Field tables for screens 03–17. The largest omission, stated on the masthead as 15 of 17 not field-traced and again above table I.
The running app. Not an omission by choice — see §07 — but it is the reason no journey-issue row exists, and it is on the masthead rather than buried.
The argument behind each screen lives in that screen's own spec table rather than being collected; the source catalogues are quoted from but not reproduced; line numbers are
given and will move; and the demo figures are treated as illustration rather than fixture.
The eleven other modules. This is the Accounts menu. Billing, payments, metering, rating, ledger and work appear only where an Accounts screen reads them.
It is fine for those to be out. It is not fine for them to be out silently.











```
