# CR-171-BRC10 — Accounts › Move-ins redesigned end to end: the list, one details view for every status (requests included), the four-step wizard and a Move-in completed screen, built from 48 images

**Raised:** 2026-10-05, by the Product Owner, in chat, over the review of the mock-up (artifact
`7RdAJVzt1tkzLBabaVoTGL`, v2 → v24), ending in a GO. The rulings are the twenty-one decision-log
rows of 2026-10-05 whose titles start *"MOVE-IN REDESIGN"*; nothing they settle is put back to the
PO (hard-won law 13).
**The drawing:** `05-prototype/movein-redesign-2026-10-05/images/01…48` (index `IMAGES.txt`),
rendered at 1440 from mock-up v24. `movein-redesign.html` is an index, never the specification
(B14 rule 42). Spacing, sizes, type and components are our UI standard's (rule 44); every figure in
an image is an illustration (rule 37).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed by `CR-156-BRC10` in
`12-governance/14-id-reservations.md`). `10-scripts/allocate.py cr` answered **170** first; between
that answer and this file a sibling pushed `CR-170-BRC10` (forgot password), so the number was
re-asked and is **171**. `--verify 171` answers TAKEN only because this lane's own commit
`1a72779ab` names it — `git log --all --grep CR-171` finds that commit and nothing else.
**Classification:** **MAINTENANCE** (`12-governance/22-product-maintenance-process.md`) — a clerk
can approve, run and look up a move-in today, so a live flow redrawn end to end is maintenance,
borrowing only the drawing step from Build (the property-Overview lesson). The parts the product
never did — co-owners with full details, a fee table, pay-now or add-to-bill, extra messages, a
cancel, a change of date, requests and finished move-ins on the list — are change and are carried
here. Screen faults found while measuring are defects (§5.3).
**Touches 🔒 money and migrations** (fee lines, payment at completion, the deposit row, the first
bill's one-time lines, a cancel that reverses money, new tables): every such file ships
**HUMAN-REVIEW-PENDING** with a row in `12-governance/09-human-review-ledger.md`, and the golden
tests do not move.
**Phase P0 is this file, lane MVI-P0.** It builds nothing and carries no version.

---

## 0 · What arrived, in the requester's words

Quoted from the decision log of 2026-10-05, newest first. Each row holds the full ruling; only the
PO's own words are repeated here.

| Mock-up | The PO, verbatim |
|---|---|
| v24 — GO | *"this scren should be similar to details view with buttons in it"* · *"ask for more make it modal"* · *"reuse common components"* · *"i want you to build prodct screens using omages from https://claude.ai/artifact/7RdAJVzt1tkzLBabaVoTGL and not text/content how many images you will use?"* · *"please start the work"* |
| after-submit table | *"all detaisla re correct - 3. What happens when the move-in is completed + units, and assets related status updayed"* |
| end-to-end scope | *"this si good, inlcude all types of customer categoties, accounts, utilitu services - 5 to 6 or 7 of them; ensure all data in DB is correctly set and all action after submission are correctly completed and data is refelcted in Units, Assets, Accounts, Payments, Cycle Route etc - rest is good"* |
| v22 | *"update details view button accrdongly"* · *"on edit of Move in request use same form Add form to edit"* · *"you will use existing code and files and modify this please confirm"* |
| v21 | *"merge this in filter"* |
| v20 | *"Preferences - can you make ui similar to Field visit - Visit needed - user will tick whether that section si reuqired and then all these as drop down - Paperless billing / Text reminders / Autopay / Portal language — Discounts to claim - Same UI and drop downs; Tax - same Ui and Exemption … date as date pickers and you have to allow uplaod certificate"* |
| v19 | *"on this actiosn should be icons"* |
| v18 | *"we dont need open account - based on status of request we will have edit, apporve, cancel, ask for more - so we have to simolify actions"* |
| v17 | *"I will also provide link for Sample — Residential · v3"* |
| v16 | *"can you merge documents with customers - and rename customer as account"* |
| v15 | *"move in details view - can you user header, tabs - our format for details view and imporve the readibility of information displayed; you can refer https://claude.ai/artifact/GYbqQEdpgxKZCm9Mp3MY3d for details view sample"* |
| v14 | *"on complete move in we should show Move In request number and show what happned in the background and then allow user ot go back to account or move in request or create another move in"* |
| v13 | *"in this table can you show meter, sub meters, behind the meters cases - show ID, meter name size and imporve interaction design - make these changes across all plans details"* · *"below fees you need payment option - pay now or add in bill"* · *"This should be table array and allow user to add more details while we show default - What goes out - call it communication or messaging"* |
| v12 | *"this should be fees and table array and allow user to add all fees for this move in - may will come from plan and some can be come from others charge codes"* |
| v11 | *"we dont have to show all the base and usage rates only mathichg one we should show"* |
| v10 | *"Plans sumary detailsa re good ; details keep it collapable - but details are not displayed propoerly - we have utility Service Rate scheudle -> wise Base Charges + Min { Size wise , hence meter and its size should be considered }, Usage cahrges based on type of rate - version, effective date, actual rates; then we have deposites - again based on account type or for all, then chagrece codes - not flat but account type or asset sizes, then discounts, taxes - so it should be corrected"* |
| v9 | *"Identity - we need to give search Customer ID button - it will search existing customer ID in system based on rules if found it will display it and link it and if it si not found then it will show that new ID will be created; If found show ID and name , link account and any outstanding"* |
| v8 | *"Mailing address - can you make this similar to Co-owners - Ui design"* |
| v7 | *"Co-owners - can you do tick and collapable ; Documents - make this table array"* |
| v6 | *"keep one field, just select the work order , dropdown searchable"* |
| v5 | *"Route 4 · Cycle 2 - can be part of premises only"* |
| v4 | *"we already have this fucntionality in request, move in ,new conenct - please chekc"* · *"we dont need this … side panel; remove it and use real estate of screen in a right way"* |
| v2 | *"can you arrange this information in logical way and imporve readibility for user and also imporve inteaction design"* · *"we can combine assets, sizes, etc with Utility services"* · *"Move-in date * - date picker"* · *"Field visit - table array element and what should be table comumnes and what all should be drop down here"* · *"Who is moving in- youneed document upload - also for person and for business - collect all required information from billing point f view customer type etc- update document"* · *"you also need co-owner and capture all details"* |
| v1 | *"this is okay"* (the three sentences leave; *"Occupied units aren't listed."*; the shown / See-more split) · *"can you prepare redesign HTML artifact for MOve IN - uisng all the points we discused"* · *"i also need detaisl view of Move In - list view of MOve in"* |

**Defaults recorded as the table stands (v22 row, law 13 — changeable by one sentence from the PO):**
Cancel stays on *Scheduled / Waiting on a read*; there is no Edit after completion; an old
outstanding balance on another account is **shown and never moved**.

## 1 · Classified

* **Maintenance** for every screen a clerk uses today: the Move-ins list, the request page's
  approve / ask / refuse, the move record, the seven-step wizard, the result panel.
* **Change** for what the product never did (list in the header). None of it reverses a money rule
  except the one collision in §7, which is **stopped** and put to the PO.
* **Defects** found while measuring: `DEF-CUS-9702`, `DEF-CUS-9703` (§5.3).

## 2 · What signed statements it touches — the supersedes chain

| # | Statement today (quoted) | Where | Superseded by | Effect |
|---|---|---|---|---|
| S1 | *"The PO ruled the control set on 2026-09-19 and on a COMPLETED record it is TWO DOORS AND NOTHING ELSE — `Open the account` and `Open the customer`"* | `MoveRecordPage.tsx` docstring; `MoveRecordPage.test.tsx` count assertion | v18 (*"we dont need open account"*) → v22 table: **Completed — More: Send a message, Print** | Both doors removed (customer, account, plan, unit, building are links in the facts); the test that pins two doors is rewritten, not deleted. |
| S2 | *"`pending` → `done`. Nothing else, and `cancelled` is deliberately absent: no door in this product cancels a move-in job"* | `move_in_jobs.py` §3; `BR-CUS-1077` | v22: **Not started — More: Cancel move-in…** | `move_in_jobs` gains `cancelled` (🔒 migration) — the state now has a writer. |
| S3 | *"A move-in nobody has approved yet is an application, not a job, so it is on the Requests tab."* | `MoveInsTab.tsx` footnote (photo `B02`) | v24 images 01–08 (To approve, Waiting on customer, Declined rows and views); v21 Status filter *To approve* | Requests that suggest a move-in join the Move-ins list; the Requests tab still lists them too (one row, two doors). |
| S4 | *"A move-in leaves this list the moment its account opens, so finished move-ins are not shown here."* | `MoveInsTab.tsx` footnote; `BR-CUS-018` reading of the tab | image 01 (*COMPLETED* row), v21 Status *Completed* | Completed and Cancelled rows stay on the list (paged, NFR-3). |
| S5 | `MOVE_IN_STEPS` = **7** steps (Find unit · Which services · Customer · Start & read · Account preferences · Deposit · Review) | `moveShared.tsx`; `BR-SHL-046` (one declared list) | v2/v4 + images 30–46: **4** steps — Unit · Customer · Billing · Review | `BR-SHL-046` stands (one list); its content changes. `move_reads.MOVE_IN_STEP_COUNT` must read the same list (`DEF-CUS-9703`). |
| S6 | B18 §5.5.1 (five tiles) and §5.5.2 (eight columns) as built: tiles *Open · Starting this week · Waiting on a reading*; columns *Reference · Account · Customer · Unit · Move-in date · Step · Reads · Deposit · State* | `MoveInsTab.tsx` | image 01: tiles *To approve · Not started · Drafts · Starting this week · Waiting on a read*; columns *Reference · Customer · Unit · Services · Move-in date · Step · Opening read · Deposit · State* + icon | B18 §5.5 superseded for the list (B14 rule 41 — the drawing wins; stated, not outbuilt). |
| S7 | The Deposit step as its own wizard step (`BR-CUS-1050`, one capability) | `MoveInWizard.tsx` step 6, `deposit.py` | v12: deposit is the first locked row of **Fees** | **Amended, not superseded**: the deposit is still one capability mounted from `deposit.py` (plan figure, no override, take / on first bill / waive by a supervisor — `OQ-CUS-12620`, `OQ-CUS-12623`). Only where it is drawn moves. |
| S8 | The request page's **Approve** dialog asks *What kind* (New connection / Move-in) and a customer match | `ServiceRequestDetailPage.tsx`; CR-031 statement 3 (the clerk decides) | v24 (1)(2): on the Move-ins details view Approve is a modal with an EFFECT line only | The kind is already *move-in* on this view; the customer match moves to wizard step 2's *Search customer ID*. The request page's own dialog stays for requests not yet classified. `BR-CUS-1095`'s four blocking checks still run and refuse inside the modal. |
| S9 | The three sentences *"Waiting 0 days — nothing is held or changed until you finish this"*, *"A move-in is recorded in the audit log by the server…"*, *"Only vacant units are listed. A unit someone still occupies has to move out first."* | `MoveInWizard.tsx` (photos `B30`, `B33`, `B41`, `B45`) | v1 *"this is okay"*: the first two leave, the third becomes *"Occupied units aren't listed."* | Ruled 2026-10-05 and **not yet built** — still on screen in 2.521.0. |
| S10 | The "This move-in" side panel | mock-up v1–v3 only | v4 *"remove it"* | Never built; nothing to remove. |
| S11 | `BR-CUS-029` (account-side plan table) | the result panel's *"No plan snapshot was recorded. The table … does not exist"* | already SUPERSEDED 2026-08-11 | The sentence is stale — `DEF-CUS-9702`. |

**No ❄️ FROZEN B4/B5 figure is changed by anything above.** The one collision with signed money law
is §7 Q1 and it is stopped, not built.

## 3 · Impact across the ten surfaces (and the drawing)

| Surface | Impact |
|---|---|
| User stories | US-CUS-004 (move-in), US-CUS-005 §S19, the request approve stories (REQ-02) and BR-CUS-1077's job story are AMENDED, none obsolete. A1 S19 keeps the wizard; the list (`S19.moveIns`) and the move record still have no A1 id — owed, reported, not invented (law 8). |
| Business rules | Amend: `BR-CUS-1077` (cancelled state), `BR-SHL-046` (content 7 → 4), B18 §5.5 (list), `BR-CUS-1050` (where the deposit is drawn), `BR-CUS-095` (checklist drawn as a table array — rule unchanged). New (P1, numbered at build): co-owner record, fee lines on a move, pay-now / add-to-bill, extra messages, cancel and change-date reversals, the status model (§6.1). Unchanged and asserted: `BR-MET-036` (occupancy derived), `BR-AST-020` (meter In stock → Installed on accepted meter-set visit), `BR-MET-1161` (address on premises; route and cycle shown on the building), `BR-CUS-089`/`1022`/`019`/`054` (match rules), `BR-CUS-092` (last four), `BR-CUS-090` (what a counter accepts), `BR-BIL-012` (first bill), `BR-PAY-010`/`012` (allocation, purpose). |
| Build steps / waves | P1 server → P2 screens → P3 proof → P4 end to end (§8). |
| Documents | `04-docs/02-decisions/18-cr030-onboarding-design.md` §5.5 (stamp superseded for the list), A1 S19 note, `03-customers/02-business-rules.md` (rows above), `13a-screen-component-map.md` (new components), CLAUDE.md: no line names the move-in flow, nothing to amend. |
| Code | Front: `MoveInsTab.tsx`, `MoveRecordPage.tsx`, `moveRecordActions.ts`, `moveRecordActionBar.tsx`, `MoveInWizard.tsx`, `moveShared.tsx`, `MoveInReadingsTable.tsx`, `moveReadsCapture.tsx`, `MoveInMessages.tsx`, `CustomerFields.tsx`, `UnitPricingPanel.tsx`, `moveInRequestBlocks.tsx`, `parkedDrafts.tsx`, `wizardPark.ts`, `ServiceRequestDetailPage.tsx` (approve dialog shared), `features/work/FieldVisitOrders.tsx` (⚠ Work's file — FIN-W lane). Back: `customers/services._move_in`, `move_reads.py`, `move_record_reads.py`, `move_in_jobs.py`, `moves.py`, `identity_match.py`, `owner_lookup.py`, `deposit.py`, `request_jobs.py`, `service_request_service.py` (`_raise_flow_work`, approve, refuse, more-info), `notifications_seam.py`, `billing/first_bill.py` 🔒, `payments` seam 🔒, migrations 🔒. |
| Test cases | `MoveInsTab.test.tsx`, `MoveRecordPage.test.tsx`, wizard dom tests, `test_br_cus_1077_move_in_job.py`, `test_br_cus_1090_move_in_job_number.py`, `test_move_in_nineteen_scenarios.py` (19 scenarios re-pointed to four steps), `test_us_bil_010_first_bill.py` (🔒, must stay green unmodified for existing cases). |
| E2E journeys | J2 (move-in), J07 (first bill), J65/J62 (field visits) assert the seven-step shape and go red correctly; re-pointed in P4. |
| Seed data | `apps.tenancy.sample_data`: the sample `Sample — Residential` plan carries **no deposit rule** (photo `B43`: *"No deposit on this plan."*) and the sample units on Kestrel Park ph. 2 carry **no meters** (`SCW-U-308`: *"No meters at this unit."*). The images' story (deposit $150, meter + irrigation sub-meter + backflow device) cannot be walked on the demo tenant until P4.01 seeds it. |
| **Open questions** | **Answers:** none outstanding (v4 withdrew the documents question). **Re-opens / touches:** `OQ-BIL-12739` (sewer without water — OPEN, untouched: the Start ticks keep today's behaviour and every M-case ticks water with sewer); `OQ-WRK-1723` (two meters on one job — OPEN; a move-in visit names one meter, as image 30 draws); `OQ-363` (worked month, non-blocking — the panel it blocks is gone with step 5). **Opens:** `OQ-BIL-12788` (§7 Q1). |
| The demo fixture | Today's sample tenant shows a list with no requests, no finished rows, and nine parked drafts after one walk (every open of *New move-in* parks a draft and spends an `MVI-` number — `BR-TEN-035` permits the gaps; photo `B02`). P4.01 seeds the seven M-cases' starting data. |
| **The drawing** | List: images 01–02. Details: 03–29 (request statuses 03–08, 18–23; move-in statuses 09–17, 24–29). Wizard: 30–47. Completed: 48. All in `05-prototype/movein-redesign-2026-10-05/images/`. |

## 4 · What is built today and becomes wrong

* **Code shipped:** every item in §5.1's table. In particular the seven-step rail, the two doors on a
  completed record (S1), the list's footnotes (S3/S4), the request page being the only place to
  approve, and the result panel (`DEF-CUS-9702`).
* **Data already written:** `move_in_jobs` rows (`pending`/`done`) stay valid; `wizard_parks` rows
  written under the seven-step shape (`step` 1–7, `values.deposit`, `values.preferences`,
  `values.reads`) must still resume — P1.03 maps them to the four steps (old 1–2 → Unit, 3 → Customer,
  4 → Unit (date, reads, visit), 5–6 → Billing, 7 → Review) and keeps every value. Move records,
  accounts, payments and reads written by the old wizard are untouched (hard rule 4).
* **Lanes building right now:** FIN-T and FIN-W (CR-168, Work). FIN-W may be in
  `features/work/FieldVisitOrders.tsx` and `apps/work/`; no task here touches either until FIN-W has
  landed (§8 rounds).

## 5 · P0 measurement — today (2.521.0) photographed beside the 48 images

**How:** worktree `/home/user/wt/w-mvi0` at tip `19bea8e5c` (frame reads **v2.521.0**), PostgreSQL 16
database `sbh_wmvi0` migrated, `seed_demo` + `load_sample_data --tenant brazosbend`, built with
`vite build --mode compose` and served by `07-frontend/server.mjs` on 5233 against `runserver` on
8101; Chromium at 1440. A move-in was run end to end through the wizard (`MVI-26-0010`, unit
`SCW-U-042`, customer `C-00052`) so the completed record and result panel could be photographed.
⚠ A first build without `--mode compose` baked the production API host into the bundle and every
sign-in failed silently on CSP — a walker's trap, not a product defect.
**Photographs:** `08-qa/movein-2026-10-05/before/` (23 files, each opened and checked non-blank).
No refused request exists in the sample data and none was made, so image 07/08 (*Declined*) has no
"today" photograph; today a refused request is the same request page (`B05`) with a *Refused* chip.

### 5.1 · Differences, screen by screen

| Image(s) | Today's photo | What today shows | What the image shows | File that draws it |
|---|---|---|---|---|
| 01 | `B01-list`, `B02-list-filter-open` | Title **Accounts**, kicker *10 tabs · Move-ins*, primary **Move-in** | Title **Move-ins**, kicker *ACCOUNTS*, primary **+ New move-in** | `AccountsListPage.tsx` (header), `MoveInsTab.tsx` |
| 01 | `B01` | Ten tabs (Accounts … Imports) | Six tabs (Requests · New connects · Move-ins · Move-outs · Transfers · Disconnects) | `AccountsListPage.tsx` — **kept at ten**, §6.2 J9 |
| 01 | `B01` | **3** tiles: Open · Starting this week · Waiting on a reading | **5** tiles: To approve · Not started · Drafts · Starting this week · Waiting on a read | `MoveInsTab.tsx` `moveInsKpis`; `move_reads.py` |
| 01 | `B01` | Search + a separate **All** button + **+ Filter** | Search full width + **+ Filter ▾** only | `MoveInsTab.tsx`, `FilterBar.tsx` |
| 01 | `B01` | Columns Reference · **Account** · Customer · Unit · Move-in date · Step · **Reads** · Deposit · State | Reference · Customer · Unit · **Services** (badges) · Move-in date · Step · **Opening read** · Deposit · State | `MoveInsTab.tsx` |
| 01 | `B01` | Row action **↗ Open** (text) on jobs; ↻ and 🗑 icons on parked drafts | One icon per row: Review (clipboard ✓) · Start (play) · Resume (pencil) · View (eye) | `MoveInsTab.tsx`, `parkedDrafts.tsx` |
| 01 | `B01` | No request rows; finished move-ins leave the list | SR- rows *To approve*; *Completed* rows | `move_reads.py` (`move_ins_queryset`) |
| 01 | `B02` | A draft row's State cell is five lines (*Parked · waiting on documents · Waiting 0 days · Remind on … · Parked by … · note*) | One pill: *DRAFT · 2 DAYS* | `MoveInsTab.tsx` `ParkedWhyCell` |
| 01 | `B02` | Step cell *1 of 6* (wizard says 7) | *3 of 4 · Billing* | `move_reads.py:642` — `DEF-CUS-9703` |
| 01 | `B02` | Three footnote sentences under the table | none (rule 33) | `MoveInsTab.tsx` |
| 02 | `B02` | Filter panel: **State** with six ticks (Not started · Scheduled · Due · Waiting · In progress · Parked) | **Status** radio (All · To approve · Open · Completed) + **Service** ticks; chips *Status: Open ✕* + *Clear all* | `MoveInsTab.tsx` filter config, `FilterBar.tsx` |
| 03–08 | `B03`, `B05` | The **request page**: *← Requests*, kicker *REQUEST SR-26-0004 · NOT YET CLASSIFIED*, six buttons (Refuse · Edit · Submit · Ask for more · Park · Approve), tabs Applicant · Documents · Audit, a two-column key/value list and a *Quoted and taken* panel | **Move-in details view**: *← Move-ins*, name + SR number, chips (status · requested/moves-in dates) + where; buttons by status (To approve: Ask for more… · Approve ✓ · More ▾ Edit / Decline…); tabs Overview · Documents · Messages · Audit; four tiles; *Request* and *Who* fact grids | `ServiceRequestDetailPage.tsx` → new request mode of `MoveRecordPage.tsx` |
| 05/06 | `B05` | Waiting-on-customer request: same six buttons | *Resend the ask* · *Approve ✓* · More ▾ | as above |
| 18 | `B18-request-approve` | Dialog *Approve SR-26-0001 · Osei, Grace*: **What kind** (New connection / Move-in), **Customer match** search, refusal *Pick what kind first.* | Modal *Approve SR-26-0014?* with one EFFECT line *Opens the move-in with this request filled in.*, Cancel · Approve ✓ | `ServiceRequestDetailPage.tsx` approve dialog |
| 19 | `B19-request-refuse` | *Refuse SR-26-0001*: Reason **dropdown**, *What to tell them*, a *Refusing does* table, a *The money* block, button *Refuse the request* | *Decline SR-26-0014?*: EFFECT *The customer is told. The request closes.*, **Reason*** textarea, danger **Decline** | same |
| 20 | `B20-request-ask-for-more` | *Ask SR-26-0001 for more*: four ticks, message, an *Asking does* table, button *Ask and queue the message* | *Ask Asha Verma for more*: EFFECT *The request waits for the reply.*, **What you need*** textarea, **Send** | same |
| 21 | `B21-request-documents` | Documents tab of the request page | *Documents* table Document · Needed · File · Added | `ServiceRequestDetailPage.tsx` |
| 22 | — | No Messages tab on a request | Messages table + *+ Send a message* | new tab (reads `ServiceRequestMessage`) |
| 23 | `B23-request-audit` | Audit tab of the request page | *Audit* table When · Who · What | `ServiceRequestDetailPage.tsx` |
| 09/10 | `B09-record-pending-job` | Pending job: kicker *MOVE-IN MVI-26-0001*, chip **Approved**, one button **Open the request →**, *No customer linked*; panels What happened · Opening reads · Money taken · Still owed | Chip **NOT STARTED**, **Start** + More ▾ (Edit · Cancel move-in…); tabs Overview · Unit & reads · Account · Billing · Work · Messages · Audit; tiles; *Details* grid; *Still open* table | `MoveRecordPage.tsx`, `moveRecordActions.ts`, `move_record_reads.py` |
| 11/12 | `B11-record-draft` | Draft: chips *In progress* · *Step 1 of 6*, **Discard draft ✓** and **Resume →** | Chip **DRAFT** · *STEP 3 OF 4*, **Edit** + More ▾ (Discard draft…) | same; `DEF-CUS-9703` |
| 13/14 | — | No such state on a record: a committed move-in with reads still to take shows as *Completed* with the list's State *Due* | **WAITING ON A READ** · *Change move-in date* · *Enter opening read* · More ▾ (Add a work order · Send a message · Cancel move-in…) | `MoveRecordPage.tsx`, `move_reads.py` |
| 15/16 | `B15-record-completed-new`, `B15-record-completed-sample` | Completed: **Open the account →** and **Open the customer →**; four panels | No buttons but **More ▾** (Send a message · Print); tabs and tiles | `MoveRecordPage.tsx` (S1) |
| 17 | — | No cancelled state | **CANCELLED** chip, no actions | S2 |
| 24 | `B15-record-completed-new` | *Opening reads* panel: Register · Reading · Read date · How, flat (E-5041, SM-7041, W-5041) | *Unit* grid (unit, address, building, owner, area · parcel, route · cycle) + *Opening reads* tree ID · Kind · Size · Last read · Opening read · Source · State, sub-meter and device nested | `MoveRecordPage.tsx`, `move_record_reads.py` |
| 25 | — | No account-holder panel; *No customer linked* in the header | *Account holder* grid, *Co-owners* table, *Documents* + Add document | new tab |
| 26 | `B15-*` | *Money taken* (Deposit: Plan requires · Taken · Still to collect) | Tiles Base charge · Fees · Paid · Still to collect; *Plan and preferences*; *Fees* table with Total; *Payment and deposit* grid (paid, receipt, deposit, carried over, still to collect, first bill) | new tab |
| 27 | — | *Still owed › Visit: Not raised* | *Work orders* table + *+ Add work order* | new tab |
| 28 | — | none | *Messages* table + *+ Send a message* | new tab |
| 29 | — | none on the record | *Audit* with All · Changes · Messages filter | new tab |
| 30 | `B30-wizard-today-1-unit-empty`, `…-unit-chosen` | Title *New occupant moving into a vacant unit.*, kicker *MOVE-IN*, *Step 1 of 7 · Find unit*, **seven**-segment rail; panel *Which unit is being taken?* with the old help sentence; a five-row *Which unit are they moving into?* panel; **Save & exit** + **Park** at the bottom left; the two ruled-out sentences under the buttons; back link reads **← Rosa Pemberton** once a unit is chosen | Title **New move-in**, **Save draft & exit** top right, **four**-segment rail; *Vacant unit* + *Occupied units aren't listed.*; unit header card with chips; **Building · Unit · Owner · History** groups; separate *Move-in date* panel; **Services and meters** table; **Field visit** table; **Park** bottom left, **Continue** bottom right | `MoveInWizard.tsx`, `moveShared.tsx`, `WizardFrame` |
| 30 | `B30-wizard-today-2-which-services` | Step 2 is its own step: a chip multi-select *Which services?* | A **Start** tick per row of *Services and meters* | `MoveInWizard.tsx` |
| 30/31/32 | `B31-wizard-today-4-start-and-reads` | Step 4 *Start date & initial meter read.*: date, *Earliest start*, an *Opening reads* table (Asset · Type · Service · Register · Last reading · Last read on · Move-in reading · Read date · Estimate), *Field visit* with a *No visit needed* tick and *+ Add work order* | Reads live in *Services and meters* (meter, size, reads-as ×1 · 6 digits, last read and date, opening read + unit), a sub-meter and a behind-the-meter row nested under their meter, an expand row with the meter's facts, and **Below the last read.** under the box | `MoveInReadingsTable.tsx`, `moveReadsCapture.tsx` |
| 32 | `B48-after-complete` (first attempt) | A reading below the last read is accepted by Continue and refused only at **Complete**: *"2 reading(s) cannot be accepted. Nothing was saved"* | Warned inline on step 1 the moment it is typed | `MoveInReadingsTable.tsx` (server refusal stays) |
| 30 | `B31` | Field visit: *No visit needed* tick (inverse) + a button | *Visit needed* tick at the panel's right; table # · Work order* (searchable) · For · Priority · Due · Window · Assign to (best-fit note) · Note; *Raised when you complete* | `features/work/FieldVisitOrders.tsx` |
| 33 | `B33-wizard-today-3-customer` | Step 3: Category and Sub-category stacked full width; Full name; Email; Phone (not required); DOB; Government ID; a **CUSTOMER NUMBER** heading over *Person or company*; SSN; Driver's license; MAILING ADDRESS tick; refusal *Say whether this is a person or a business* if not picked | Person/Company segmented at the top; Customer type* + Sub-type side by side; Full name; Email + Phone* (*Texts go to this number.*); Contact by + Date of birth; separate **Identity** panel (SSN · Driver's license · Government ID, *Search customer ID*); **Co-owners** tick + cards; **Documents** table; **Mailing address** tick + card | `CustomerFields.tsx`, `MoveInWizard.tsx` |
| 34–37 | — | No search; the request page's dialog is the only match | *Search customer ID* → Existing / Possible / New / Linked panel with accounts, state and outstanding | new component; `owner_lookup.py` |
| 38 | — | Co-applicant is three fields on a request/account (name, email, phone) | Co-owner card: Full name*, Relationship, DOB, SSN, Driver's license, Phone, Email, Contact by, Photo ID upload, *Also responsible for the bills* | new |
| 39 | — | Documents are not on the move-in wizard; they live on the request | Documents table array with the move-in checklist's required rows locked | `DocumentCapture`, `BR-CUS-095` checklist |
| 40 | — | Company: name + Tax ID only | Legal name*, Trading as, Business type*, EIN*, Registered in; **Contact person**; **Owners and officers**; **Bills go to** + PO on bills | `CustomerFields.tsx` + new fields |
| 41 | `B41-wizard-today-5-preferences` | Step 5 *Account preferences.* is a ~2,000-px always-open dump of the plan (code, status, base charges, services, every rate schedule's tiers, every discount's eight conditions incl. MUNICIPAL for a residential account) | *Plan* summary line (Plan · Version on date · Base charge · Deposit rule) + **▸ See full rates**; *Preferences* tick + four dropdowns; *Discounts* tick + table; *Tax* tick + exemption fields | `UnitPricingPanel.tsx`, `MoveInWizard.tsx` |
| 42 | `B41` | Unit prices at 2 places ($4.24, $6.89, $0.135) | Unit prices up to 4 ($4.2350) per CLAUDE.md hard rule 2's exception; only this move-in's rows; asset tree per service | `UnitPricingPanel.tsx` → `planSections/PlanSections.tsx` |
| 41/43/44 | `B43-wizard-today-6-deposit` | Step 6 *The deposit.* — *No deposit on this plan. Carried over. CARRY-FORWARD No earlier deposit can be found.* | **Fees** table (deposit + plan fees locked, *+ Add fee*, Total) and **Payment** (Pay now / Add to bill; method, amount, check number, received; *$115.00 goes on the first bill.*) | `MoveInWizard.tsx`, `deposit.py` |
| 45/46 | `B45-wizard-today-7-review` | *Confirm move-in.* — one list of 13 label/value rows; *What goes out* table (Send · What it says · To · Channel · Template · When) with the service agreement greyed; *Field visit* line jammed under it | Four sections Unit · Customer · Billing (each with *✎ Edit*) and **Messaging** table array (Send · Message* · To · Channel · When, *+ Add message*, *2 will send*); **Complete move-in ✓** | `MoveInWizard.tsx`, `MoveInMessages.tsx` |
| 47 | — | Editing reopens via *Resume* with the same *New occupant…* title | Title **Edit move-in · MVI-26-0011** | `MoveInWizard.tsx` |
| 48 | `B48-after-complete` | *Move-in complete.* — *What was written* (account, unit, previous account, customer number, two sentences, read count), *Field visit*, **What the server could not do** (two false absences — `DEF-CUS-9702`), *Open the new account*; **no MVI number shown** | **Move-in completed** · COMPLETED · **MVI-26-0011** *From request SR-26-0014 · name · unit*; *What happened* ticked list (customer, account + plan link, services, reads, unit Vacant → Occupied, co-owners, documents, work orders, fees, payment + receipt, messages); *+ Start another move-in* · *Open the move-in* · **Open the account →** | `MoveInWizard.tsx` result panel |
| frame | all | App frame (sidebar, top bar) | Images are drawn without the frame | not a difference — the frame is our UI standard's (rule 44) |

### 5.2 · What the sample data could not show

Image figures (deposit $150, a 5/8" meter with an irrigation sub-meter and a backflow device, fees
$175, check 1043) are illustrations (rule 37) — but the *shapes* need data: the demo plan has no
deposit rule and the Kestrel Park units have no meters. P4.01 seeds the M-case starting data so the
P3 walk can photograph every image's shape.

### 5.3 · Defects filed while measuring (filed before anything is fixed)

| Id | What | Fixed by |
|---|---|---|
| `DEF-CUS-9702` | The result panel says *"with no customer record there is no same customer to carry from"* on the same screen that created customer `C-00052`, and *"The table that holds an account's plan does not exist"* about a design that was superseded on purpose (`BR-CUS-029`) | P2.16 (completed screen) + P1.21 (the two codes stop being served) |
| `DEF-CUS-9703` | Drafts read *1 of 6* on the list and the record while the wizard reads *of 7* (`move_reads.MOVE_IN_STEP_COUNT = 6`) | P1.02 (one list) |

**Observed, not filed (by design or already ruled):** the back link reading *← Rosa Pemberton* (the
previous occupant) once a unit is chosen — the wizard is account-scoped through the outgoing account,
and the redesign's back link is *← Move-ins* (P2.10); the two ruled-out sentences (S9 — ruled
2026-10-05, not yet built); every open of *New move-in* parking a draft and spending a number
(`BR-TEN-035` permits gaps; the list's *Drafts* tile will show them).

## 6 · Every element in the images — reused, modified or new

**Verified** says how the claim was checked: **code** (read the file or its exports in this
worktree), **screen** (seen in a `before/` photo), **claim** (named by a ruling or a docstring and
not yet opened — P1/P2 opens it first and corrects this table if wrong).

| # | Element | Images | Verdict | From | Verified |
|---|---|---|---|---|---|
| E01 | Page header, kicker ACCOUNTS, title Move-ins, **+ New move-in** | 01 | Modify | `PageHeader` (title/kicker/primaryAction), `AccountsListPage` | code + screen |
| E02 | Accounts tab bar | 01 | Reuse (kept at ten — §6.2 J9) | `AccountsListPage` tabs | screen |
| E03 | Five KPI tiles | 01 | Modify | `KPIStrip`; `move_reads` KPI block | code + screen |
| E04 | Search box | 01 | Reuse | `FilterBar` search | screen |
| E05 | **+ Filter ▾** with Status radio + Service ticks | 02 | Modify | `FilterBar` (options panel exists, `DEF-442`) | code + screen |
| E06 | Removable chips + Clear all | 02 | Reuse | `FilterBar` chips | code (header `DEF-442`) |
| E07 | Table columns incl. Services and Opening read | 01 | Modify | `DataTable` + `MoveInsTab` config | screen |
| E08 | Service badges W/S/E | 01 | Reuse | `ServiceChips` | screen (`B45` badges) |
| E09 | Eight status pills | 01, 03–17 | Modify | `StatusPill` tones; new vocabulary | code |
| E10 | One icon action per row (Review/Start/Resume/View) with tooltip + named label | 01 | Modify | `RowActions`/`RowAction`, `icons.tsx` | code |
| E11 | Pager | 01 | Reuse | `ListPager` | screen |
| E12 | Request rows on the list | 01 | New (server rows) | `move_ins_queryset` + `service_requests` | code |
| E13 | Completed / Cancelled rows | 01 | New (server rows) | `move_records`, `move_in_jobs` | code |
| E14 | No footnotes | 01 | Modify (remove) | `MoveInsTab` | screen |
| E15 | Back link, name title, reference beside it | 03–29 | Modify | `PageHeader` (`backTo`, `title`, `titleAfter`) | code |
| E16 | Status chip + date chip + where line | 03–29 | Modify | `PageHeader.status`, `StatusPill`, `Chip` | code |
| E17 | Actions by status (primary, secondary, More ▾) | 03–17 | Modify | `moveRecordActions.ts`, `moveRecordActionBar.tsx`, `PageHeader` action slots | code |
| E18 | More ▾ menu with a danger item | 04–16 | Reuse | `RowActionsMore` (+ `danger`) | code |
| E19 | Tabs with counts | 03–29 | Reuse | `PageHeader.tabs` (`PageHeaderTab`, as `PlanDetailHeader`) | code |
| E20 | Four figure tiles that open their tab | 03–17, 26 | Reuse | `KPIStrip` (`press`) | code |
| E21 | Three-column fact grids (Request, Who, Details, Unit, Account holder, Plan and preferences, Payment and deposit) | 03–26 | Reuse | `FactBlock` (as Plans details) | claim (3-col layout) |
| E22 | *Still open* table | 09–17 | New content | `PlainTable` | code |
| E23 | Approve modal with EFFECT | 18 | Modify | `ConfirmDialog` + `ConsequenceBox`; `POST /service-requests/{id}/approve` | code + screen |
| E24 | Decline modal, Reason* | 19 | Modify | `ConfirmDialog` (`confirmVariant` danger); `POST …/refuse` | code + screen |
| E25 | Ask for more modal, What you need* | 20 | Modify | `ConfirmDialog`; `POST …/transitions` (more_info) | screen |
| E26 | Resend the ask | 05 | New | re-queue `notifications_seam.queue_request_more_info` | code (function exists) |
| E27 | Reopen (declined) | 08 | ~~Reuse~~ ~~HELD~~ **New (built 2.527.0)** | ⚠ **the claim was wrong (checked by MVI-REQ, P1.06):** `reopen` was retired by the PO on 2026-09-19 (`service_request.RETIRED_ACTIONS`; refuse is terminal) — no transition exists to reuse. Put to the PO as `OQ-CUS-12789`; **CLOSED → (a) 2026-10-05 and built by MVI-FLOW**: `MOVE_IN_TRANSITIONS`, `service_request_service.reopen_declined_move_in`, `POST …/reopen` (§9.FLOW). | code |
| E28 | Documents tab table | 21 | Reuse | `components/documents` (`DocumentTable`), `GET …/documents` | code (files) |
| E29 | Messages tab + Send a message | 22, 28 | Modify | `ServiceRequestMessage`, `notifications_seam.queue_account_message` | code |
| E30 | Audit tab, All/Changes/Messages | 23, 29 | Modify | request Audit tab, `SegmentedField`/`SubTabs` | screen |
| E31 | Unit & reads tab (unit grid + reads tree) | 24 | Modify | `move_record_reads.py`, `UnitAssetsPanel` groups | code + screen |
| E32 | Account tab (holder, co-owners, documents) | 25 | Modify (holder, documents) + New (co-owners) | account/customer reads; `AccountDocument` | code |
| E33 | Billing tab (tiles, plan and preferences, fees, payment and deposit) | 26 | Modify (deposit, plan) + New (fees) | `move_record_reads` *Money taken*, `deposit.py` | code + screen |
| E34 | Work tab + Add work order | 27 | Reuse | `components/RaiseFieldWork.tsx`, work orders by account | code (file) |
| E35 | Change move-in date | 13 | New | — | — |
| E36 | Enter opening read | 13 | Modify | `customers.seams.commit_event_reads` + `MoveInReadingsTable` in a modal | code |
| E37 | Cancel move-in | 10, 14 | New | — (S2) | code |
| E38 | Discard draft | 12 | Reuse | `ParkedDiscardDialog` | code + screen |
| E39 | Print | 16 | New | — (no move-record print exists) | claim |
| E40 | Four-step rail with ticks | 30–47 | Modify | `WizardFrame`, `MOVE_IN_STEPS` | code + screen |
| E41 | Title *New move-in*, Save draft & exit top right, Park / Back / Continue | 30–47 | Modify | `WizardFrame`, `useWizardPark` | screen |
| E42 | Vacant unit select + *Occupied units aren't listed.* | 30 | Modify | `MoveInWizard` step 1 | screen |
| E43 | Unit header card + chips | 30 | New layout | unit move-in facts read | screen |
| E44 | Building · Unit · Owner · History groups (route · cycle on the building, *Billed while vacant*, *Plan changed 2 times · see*) | 30 | Modify | unit facts read; `unit_plan_assignments`; `BR-CUS-1116` | claim (route/cycle/area/parcel on one read) |
| E45 | Move-in date picker | 30 | Reuse | `DatePickerField` | code + screen |
| E46 | Services and meters table (Start tick, meter tree, opening read + unit) | 30–32 | Modify | `MoveInReadingsTable` (`EditableTable`) + step 2 `ChipMultiSelect` → `TableArray` | code + screen |
| E47 | Meter facts on expand | 31 | New | assets read | claim |
| E48 | *Below the last read.* inline | 32 | New (screen) | server refusal exists (`BR-MET-129`) | screen (`B48` first attempt) |
| E49 | Field visit table, one searchable *Work order* column | 30 | Modify | `features/work/FieldVisitOrders.tsx` | code |
| E50 | Person / Company | 33, 40 | Reuse | `SegmentedField` | code + screen |
| E51 | Customer type + Sub-type side by side | 33 | Modify | `CustomerFields` | screen |
| E52 | Person fields incl. Contact by, Phone* | 33 | Modify | `CustomerFields` | screen |
| E53 | Identity panel + Search customer ID | 33–37 | Modify | `POST /customers/match` (`owner_lookup`, `identity_match.recognise`) | code |
| E54 | Found / Possible / New / Linked panel with accounts + outstanding | 34–37 | New (component) + Modify (match answer gains accounts and balances) | `owner_lookup.lookup` returns `verdict` + `candidates` only | code |
| E55 | Co-owners tick + collapsible cards + full fields | 33, 38 | New | — (today three `co_applicant_*` fields) | code |
| E56 | Documents table array | 33, 39 | Modify | `DocumentCapture`, `ServiceRequestDocumentRequirement` (`move_in`) | code |
| E57 | Mailing address tick + card | 33, 39, 40 | Modify | `UsAddressFields`, `customers.addresses kind='mailing'` | code |
| E58 | Company: Legal name, Trading as, Business type, EIN, Registered in | 40 | Modify (name, EIN) + New (trading as, business type, registered in) | `Customer.display_name`, tax id | code (no such columns today) |
| E59 | Contact person | 40 | New | `Contact` model exists (reuse as storage) | code |
| E60 | Owners and officers cards | 40 | New | same table as E55 | — |
| E61 | Bills go to + PO on bills | 40 | New | — | code (no column) |
| E62 | Plan summary line + See full rates | 41 | Modify | `UnitPricingPanel`, `GET /units/{id}/pricing` | code + screen |
| E63 | Full rates by service with asset tree; deposit; charges; discounts; taxes | 42 | Modify | `features/rating/planSections/PlanSections.tsx` (CR-167's shared component) narrowed to this move-in | code (file) |
| E64 | Preferences tick + four dropdowns + Autopay from | 41 | Modify | `PortalLanguageField`, account flags, `payments.StoredPaymentInstrument` | code |
| E65 | Discounts tick + table array | 41 | Modify | `moveInRequestBlocks.DiscountClaimForm`, `rating` discount enrolments | code |
| E66 | Tax exempt tick, exemption, cert no, issued, expires*, certificate* | 41 | Modify (`tax_exempt`, `_ref`, `_expires` exist) + New (exemption type, issued, file link) | `Account` columns, `AccountDocument` | code |
| E67 | Fees table array (plan rows locked, + Add fee by charge code, Total) | 41, 43 | New | rating charge codes, `deposit.standard_for_unit` | code |
| E68 | Payment: Pay now / Add to bill, part payment | 41, 43, 44 | Modify | `deposit.py` take block, `payments.services.record_payment` | code |
| E69 | Review in four sections with ✎ Edit | 45 | Modify | `MoveInWizard` review step | screen |
| E70 | Messaging table array + Add message | 45, 46 | Modify (defaults) + New (extra messages) | `MoveInMessages`, `GET /move-ins/messages` | code + screen |
| E71 | Complete move-in ✓ | 45 | Reuse | `WizardFrame` final button | screen |
| E72 | *Edit move-in · MVI-…* | 47 | New (mode) | `MoveInWizard` + `?parked=` | — |
| E73 | Move-in completed screen | 48 | Modify | result panel in `MoveInWizard` | screen |

**Counts — 73 elements:** **Reuse 16** (E02 E04 E06 E08 E11 E18 E19 E20 E21 E27 E28 E34 E38 E45
E50 E71) · **Modify 35** (E01 E03 E05 E07 E09 E10 E14 E15 E16 E17 E23 E24 E25 E29 E30 E31 E36 E40
E41 E42 E44 E46 E49 E51 E52 E53 E56 E57 E62 E63 E64 E65 E68 E69 E73) · **New 16** (E12 E13 E22
E26 E35 E37 E39 E43 E47 E48 E55 E59 E60 E61 E67 E72) · **part modified, part new 6** (E32 E33 E54
E58 E66 E70). **Verified: 65 of the 73 were checked in code or on a photograph in this worktree;
8 are not yet** — five claims (E21's three-column layout, E27's reopen, E39's print, E44's one
read for route/cycle/area/parcel, E47's meter-facts read) and three rows with nothing to check
because the thing does not exist (E35, E60, E72). The task that consumes each opens it first and
corrects this table if the claim is wrong.

**New tables or columns — only where nothing exists (v22):** (1) **co-owners / owners and
officers with full details** (one table, a `kind`), (2) **fee lines on the move record** (and their
parked shape before commit), (3) **extra messages** on a move-in (scheduled sends beyond the two
defaults). Columns on existing tables, each because no column holds the fact today: company
*trading as*, *business type*, *registered in*, *PO on bills*, *bills go to*; tax-exemption *type*
and *issued*; `move_in_jobs.state` gains `cancelled`; the Autopay source points at a
`StoredPaymentInstrument`. Everything else is existing code modified.

### 6.1 · The status model the list and the details view read (our judgment, recorded)

One server function returns one status per row, so the list's pill, the details chip and the
actions can never disagree (the `DEF-127` shape):

| Status | Row is | Rule |
|---|---|---|
| To approve | a `service_requests` row, `submitted`/`under_review`, whose resolver says *served, vacant* (the request page's *Suggested: Move-in*) | the existing suggestion, not a new classifier |
| Waiting on customer | the same, `more_info` | |
| Declined | the same, `refused` | |
| Not started | `move_in_jobs.state = pending` with no draft | `BR-CUS-1077` |
| Draft | a `wizard_parks` row, flow `move_in` | `BR-SHL-048` |
| Scheduled / Waiting on a read | a `move_records` row whose opening reads are not all taken (today's list word *Due*) or whose move-in visit is open | reads cell `taken`/`due` already derived |
| Completed | a `move_records` row with every read taken | |
| Cancelled | `move_in_jobs.state = cancelled`, or a cancelled committed move-in (P1.14) | S2 |

A request that suggests *new connection* never appears here. Pagination and sort stay on the server
(NFR-3, NFR-5): no cap, no unpaginated read.

⚠ **AMENDED BY P1.04 (lane MVI-LIST, decision log 2026-10-05 *"MOVE-IN REDESIGN P1.02–P1.05"*):**
*Waiting on a read* names a READ only — *"or whose move-in visit is open"* is dropped (the visit is
on *Still open*); a move-in whose account has closed is *Completed*; a pending job whose request a
draft names reads *Draft*; a legacy draft account with no move record reads *Not started*. The
built table is §9.LIST.

### 6.2 · Other judgments of ours (recorded in the decision log, not asked — law 13)

* **J1 · Approve on the details view raises the pending job and stays on the page**, which turns
  *Not started* with **Start** (images 09/10). The EFFECT line *"Opens the move-in with this request
  filled in"* describes what **Start** then does. `BR-CUS-1077` unchanged: no account at approval.
* **J2 · Decline and Ask for more keep their servers.** The modal's one required text is the
  message to the customer; *Decline* sends reason code `other` with that text where the server
  needs a code (P1.06 checks `service_request_refuse`'s contract first and records what it found). **Checked (MVI-REQ, 2026-10-05):** `reason` is required, `reason_code` is optional (absent → NULL) and limited to the five — the server never needs a code; Decline sends `other` anyway so every move-in decline is countable. Full contract §9.REQ.
* **J3 · Edit on a request** (*To approve*, *Waiting on customer*) opens the four-step form filled
  from the request (v22 *"use same form Add form"*); *Save draft & exit* writes the request's own
  fields back to the request and parks the rest; it never approves.
* **J4 · Fees taken "today" are a payment, not a fee bill.** Every fee row lands on the **first
  bill** as a one-time line (`BR-BIL-012` already carries the deposit and the connection charge);
  money taken at the counter is recorded at **Complete** through `payments.record_payment` —
  purpose `deposit` for a deposit paid in full, purpose `bill`/prepay for the rest — and the first
  bill reads it (`BR-PAY-012`). Worked: fees DEPOSIT $150.00 + CONNECT $25.00 + RUSH $40.00 =
  **$215.00**; *Pay now* $100.00 by check → the first bill carries $215.00 of one-time lines and a
  $100.00 payment, and the clerk reads *"$115.00 goes on the first bill."* (image 43). A part payment
  never takes the deposit partly: the deposit is *required, on the first bill* (`deposit.py`'s
  existing answer) and the $100.00 is allocated by `BR-PAY-010` at issue. No tax changes (§7 Q1
  decides the one place it could). 🔒
* **J5 · A fee the clerk adds is priced from its charge code** (v12's recorded reading), on the first
  bill; `BR-BIL-007` (a fee is a tenant charge code) covers it. Extending `first_bill.OneTimeLines`
  beyond deposit + connection to *any* code the move recorded is a 🔒 engine change with a golden
  test for the new case and the existing first-bill tests unmodified.
* **J6 · Cancel after Complete reverses only what has a reversal, as new rows** (hard rule 4): the
  account is closed as *move-in cancelled* before any bill issues (refused once one has); payments
  taken are refunded through the existing `Refund` path; open work orders are cancelled through
  Work's cancel; opening reads stay (append-only, and they are true readings); the unit reads Vacant
  again because occupancy is derived (`BR-MET-036`). The confirm modal lists exactly those four
  lines before the clerk presses (the PO's *"the build states what that reverses before it ships"*).
  Worked: Nilesh G, $175.00 by check 1043, WO-0062 scheduled → cancel: account closed, refund
  $175.00 queued, WO-0062 cancelled, unit Vacant. 🔒
* **J7 · Change move-in date** is allowed on *Scheduled / Waiting on a read* until the first bill
  issues, and moves the account's start, the service agreements and the default due date of the
  move-in visit; refused by name after a bill has issued.
* **J8 · Old outstanding balances are shown, never moved** (v9 row, ruled default).
* **J9 · The Accounts page keeps its ten tabs.** Image 01 draws the six move-related ones; removing
  Accounts, Complaints, Services and Imports from the Accounts register is outside this CR and would
  break `BR-CUS-1049`. Recorded as a deliberate difference from the drawing.

## 7 · Money and signed-rule check — one collision, stopped

**Q1 · `OQ-BIL-12788` — is a fee taken at move-in taxed?** Image 26 shows CONNECT *Taxable: Yes*,
and image 42's Taxes block reads *City utility tax 2.00% on Water, Sewer, CONNECT*. The signed rules
give two different answers for the same fee depending on how it is paid:

* On the **first bill** (*Add to bill*): ❄️ B4.2 — *"fees and late charges are NOT taxed"*, and the
  2026-09-30 addendum says *"a first bill's connection charge … is still kept out of the base by
  KIND"* → CONNECT **$25.00**, tax **$0.00**.
* Raised on its own as a **fee bill** (one way to take it *today*): the 2026-09-30 addendum taxes a
  fee bill whose code is marked taxable → $25.00 × 2.00% = **$0.50**, total **$25.50**.

**Options:** **(a)** never taxed at move-in either way — fees taken today are a prepayment of the
first bill's one-time lines (J4), no re-sign, and the *See full rates* Taxes block stops listing
CONNECT; **(b)** taxed either way — re-sign ❄️ B4.2 so a taxable code is taxed on a first bill too
($25.50 both ways); **(c)** leave the two paths as the rules fall ($25.50 today, $25.00 on the first
bill). **Recommendation: (a).** It needs no re-sign, the customer pays the same whichever button the
clerk presses, and it is what J4 builds. **Nothing is built on this until the PO answers;** P1.12
stubs the tax decision with `raise NotImplementedError("OQ-BIL-12788")` only on the path that would
tax, and builds everything else.

**Checked and NOT colliding:** the deposit (plan figure, no override, take / first bill / waive by a
supervisor — `deposit.py`, `OQ-CUS-12620`, `OQ-CUS-12623`); Fire in M5 (`$84.00` on one line,
asserted, never re-derived); a part payment (`BR-PAY-010` allocation, *tax first* 2026-08-12);
*Add to bill* (lines on the first bill, `BR-BIL-012`); unit prices at up to 4 places and totals at 2
(hard rule 2, PO 2026-10-02); occupancy derived (`BR-MET-036`); meter status (`BR-AST-020`).

## 8 · The tasks — 114 in five phases, rounds and lanes, versions and rollback

Status column per `13-change-process.md` (2026-09-02). Image numbers are the drawing each task is
built from; the brief for a screen task QUOTES its image's labels in order (2026-09-10 rule) and
names the UI skill at `.claude/skills/react-tailwind-css-ui-generator/SKILL.md`. 🔒 = HUMAN-REVIEW-
PENDING with a ledger row; **M** = carries a migration (🔒 migration ordering).

### P0 — measure and plan (lane MVI-P0) — 6 tasks

| # | Task | Files | Status |
|---|---|---|---|
| P0.01 | Run 2.521.0 on PostgreSQL with sample data and photograph every reachable state at 1440 | `08-qa/movein-2026-10-05/before/` (23) | **done** (`1a72779ab`) |
| P0.02 | Side-by-side differences by screen | this file §5.1 | **done** |
| P0.03 | Element inventory reused / modified / new, verified | §6 | **done** |
| P0.04 | Defects found while measuring, filed first | `DEF-CUS-9702`, `DEF-CUS-9703` | **done** |
| P0.05 | Supersedes chain, impact, built-and-wrong, money check | §2–§4, §7 | **done** |
| P0.06 | This CR, its index row, its reservation row, the decision row, `OQ-BIL-12788` | `12-governance/…` | **done** |

### P1 — server (30 tasks)

| # | Task | Files | Images | Lane | Status |
|---|---|---|---|---|---|
| P1.01 | **M** 🔒 One customers migration for every new fact: co-owner table (`kind` co_owner/officer, full fields, encrypted SSN/licence with blind index, photo-ID document link, responsible-for-bills); company columns (trading as, business type, registered in, PO on bills, bills go to); tax-exemption type + issued; `move_in_jobs.state` += `cancelled`; move fee lines table; move extra-messages table. RLS FORCE on every new table; down path named | `customers/migrations/0080_cr171_p1_01_move_in_redesign.py`, `customers/models.py`, `move_in_jobs.py`, `co_owner_models.py`, `move_in_extras.py` | 25, 26, 38, 40, 41 | SCHEMA | **done** (§9.1; version in §10) |
| P1.02 | One step list: `MOVE_IN_STEPS` = Unit · Customer · Billing · Review served to the list and record (`DEF-CUS-9703`) | `move_reads.py`, `moveShared.tsx` (constant only) | 01, 11 | LIST | **done** — server half (§9.LIST); the front-end constant flipped with P2.15 (2.532.0) |
| P1.03 | Parked drafts written under seven steps resume in four, every value kept | `tenancy/wizard_parks.py`, `wizardPark.ts` hydrate | 11, 47 | LIST | **done** (§9.LIST; map in `move_reads.py` + `moveShared.tsx`, wired by P2.15) |
| P1.04 | The status model §6.1 as one function; `GET /move-ins` serves requests, drafts, jobs, scheduled, completed, cancelled; five KPI counts; Status + Service filters; search by customer, unit, MVI/SR; server paging and sort | `move_reads.py`, `api.py` `move_ins_list` | 01, 02 | LIST | **done** (§9.LIST, `move_in_list.py`) |
| P1.05 | `GET /moves/{ref}` resolves an `SR-` reference to its request (statuses To approve / Waiting / Declined) and serves tiles, fact grids, tab counts, Still open | `move_record_reads.py` | 03–17 | LIST | **done** (§9.LIST) |
| P1.06 | Approve / Decline / Ask for more / Resend / Reopen from the move-in view through the existing request doors; check `refuse`'s reason-code contract and record it (J2) | `service_request_service.py`, `service_request_api.py`, `notifications_seam.py` | 18–20, 05, 08 | REQ | **done** (2.524.0) — Reopen ~~held on `OQ-CUS-12789`~~ closed → (a) and **built by FLOW** (2.527.0) |
| P1.07 | Request Messages tab read; request audit read for the move-in view | `applicant_message_models.py`, `service_request_api.py` | 22, 23 | REQ | **done** (2.524.0) |
| P1.08 | Edit a request through the four-step form (J3): request fields written back, rest parked | `service_request_service.py`, `wizard_parks.py` | 47 | REQ | **done** (2.524.0) |
| P1.09 | Search customer ID: `POST /customers/match` answer gains each candidate's accounts (number, address walked from premises, state, outstanding balance derived) and the total; Found / Possible / New verdicts by `BR-CUS-089`/`1022`/`019`; last four only (`BR-CUS-092`) | `owner_lookup.py`, `identity_match.py`, customer selectors | 34–37, 40 | IDN | **done** (2.522.0, §9.IDN) · verdicts re-cut to New Connection's Q5 by PO ruling (2.537.0, lane RULINGS) |
| P1.10 | Co-owners and owners/officers written at Complete and read on the Account tab | `services._move_in` (co-owner block), new co-owner service | 25, 38, 40 | IDN | **done** (2.528.0, §9.IDN-2; read on the Account tab is P1.05/P2.10's) |
| P1.11 | Company fields, contact person, bills go to, PO on bills written and read (PO printed on bills is a billing READ, not a new rule) | `services.py`, `customers` serializers | 40, 45 | IDN | **done** — read 2.522.0 (§9.IDN), widened and written 2.528.0 (§9.IDN-2) on 0080's columns |
| P1.12 | 🔒 Fee lines: the plan's fees for this unit and account type first (deposit via `deposit.standard_for_unit`, charge codes by account type or meter size), + any charge code priced from its code, open-amount codes typed; parked before commit, written on the move record at Complete; tax decision stubbed `NotImplementedError("OQ-BIL-12788")` on the taxing path only | new `customers/move_fees.py`, `deposit.py` | 41, 43 | MONEY | **done** (2.529.0, §9.MONEY) — no tax stub: `OQ-BIL-12788` closed (a), never taxed |
| P1.13 | 🔒 Payment at Complete (J4): Pay now (method, amount, check/card last four/reference, received) or Add to bill; deposit-purpose only when the deposit is paid in full; receipt number returned | `services._move_in`, payments seam, `deposit.py` | 41, 43, 44, 26 | MONEY | **done** (2.529.0, §9.MONEY) |
| P1.14 | 🔒 First bill carries every fee line the move recorded (J5) and reads the counter payment; golden test for the new line kinds; existing `test_us_bil_010_first_bill.py` unmodified | `billing/first_bill.py`, `billing/payments_seam.py` | 26 | MONEY | **done** (2.529.0, §9.MONEY) — the lines are kind `fee` (no new KIND), so no golden GT moves; the J4 $215.00 is asserted through `calculate_first_bill` in `test_cr171_p1_14_first_bill_fees.py`; `test_us_bil_010_first_bill.py` unmodified and green; `DEF-BIL-9709` fixed |
| P1.15 | Preferences (paperless, text reminders, autopay + source instrument, portal language), discounts claimed (plan's own, one per kind), tax exemption with certificate stored as an account document | `services._move_in`, `rating` enrolment seam, `AccountDocument` | 41, 44 | MONEY | **done** (2.529.0, §9.MONEY) — a clerk's discount claim and exemption certificate were HELD for a System Admin (rating's RBAC) · **from 2.539.0 (lane RULINGS) the clerk's claim is ENROLLED and the certificate RECORDED at once**, PO ruling 2026-10-05 (b) *"Let billing clerks record it themselves"* · **from 2.546.5 (lane RULINGS-2, `DEF-CUS-9724`) the certificate no longer sets the account's blanket `tax_exempt`** — PO ruling (A) *"An exemption removes only the tax named on its certificate. The church pays $6.25."* |
| P1.16 | `GET /units/{id}/pricing` narrowed to this move-in: this meter size's base/min, this account type's deposit, the charges that apply, the discounts this customer can claim, the taxes that apply; the asset tree per service (meter → sub-meter → device); unit prices at up to 4 places | `rating` pricing read, `customers` unit read | 41, 42 | MONEY | **done** (2.529.0, §9.MONEY) — served as `GET /move-ins/pricing` (customers), not a parameter on metering's route; `DEF-RAT-9708` fixed |
| P1.17 | Unit facts in one read: building (type, inside limits, area, parcel, verified, route, cycle), unit (type, floor, area, common), owner (name, account, billed while vacant), history (first occupant / previous, plan changes count) | unit move-in read | 30 | FLOW | **done** (2.531.0, §9.FLOW) — `GET /units/{id}/move-in-facts` |
| P1.18 | Services and meters in one read with the Start choice (`BR-CUS-1101`), sub-meter and device rows, reads-as, last read, *Follows water*; below-last-read answered per row before Complete | `move_reads.py`, `customers.seams`, `MoveInReadingsTable` data hook | 30–32 | FLOW | **done** (2.531.0, §9.FLOW) — `GET /units/{id}/move-in-meters` + `POST …/check`; *Follows water* is not served (a rating fact) — the row says unmetered |
| P1.19 | Field visit: one *Work order* field naming a template and its type; best-fit assignee advice; raised at Complete through `_raise_flow_work` (one function — the copy in `service_request_service.py` reconciled) | `services._raise_flow_work`, `service_request_service._raise_flow_work` | 30, 27 | FLOW → WIZ-UNIT | **done** (2.538.0) — the row names its template (checked against `?flow=move_in`'s offer), its meter (*For*) and a window; one `_raise_flow_work`; best-fit advice is Work's `GET /work/candidates` read by the screen (§15) |
| P1.20 | Messaging: the two defaults (`move_in_welcome`, `service_agreement`) untickable not removable; extra messages to customer / co-owner / unit owner by email, text, letter, portal, on complete / day before move-in / on the date / day before the visit; queued through `notifications_seam` | `notifications_seam.py`, `MoveInMessages` data, new extra-messages rows | 45, 46, 28 | FLOW | **done** (2.531.0, §9.FLOW) — on-complete messages to the customer are queued; scheduled sends and co-owner / unit-owner rows are written as PLANNED with their reason (no scheduler, no address door). ⚠ **The second default, the service agreement, is listed and never queued** — `DEF-CUS-9743` (P3.02) |
| P1.21 | Complete answers *What happened* (customer created/linked, account + plan version, services + date, reads per meter, unit Vacant → Occupied, co-owners, documents, work orders + assignee, fees, payment + receipt or amount left, messages) and the `MVI-` and `SR-` numbers; the two stale absences stop being served (`DEF-CUS-9702`) | `services._move_in`, `services.MOVE_IN_UNAVAILABLE` | 48 | FLOW | **done** (2.531.0, §9.FLOW) — `what_happened`, `request_no`; `DEF-CUS-9702` fixed |
| P1.22 | 🔒 Cancel move-in: Not started (job → cancelled) and Scheduled / Waiting on a read (J6 reversals as new rows; refused once a bill has issued) | `move_in_jobs.py`, `moves.py`, `services.py`, payments refund seam, work cancel seam | 10, 14, 17 | FLOW | **done** (2.531.0, §9.FLOW) — committed cancel with a held deposit stubbed on `OQ-CUS-12790` · **`OQ-CUS-12790` (a) BUILT 2.541.0 (lane RULINGS):** a held deposit is released to credit (`payments.deposit_release`, DR 2300 / CR 2400) and refunded WITH the rest as ONE refund request — Nilesh's $150.00 + $25.00 = **$175.00** |
| P1.23 | Change move-in date (J7) | `services.py`, `moves.py` | 13 | FLOW | **done** (2.531.0, §9.FLOW) — the visit's due date is listed, not moved (decision log) |
| P1.24 | Enter opening read after Complete through metering's event door | `customers.seams.commit_event_reads`, `move_record_reads.py` | 13, 24 | FLOW | **done** (2.531.0, §9.FLOW) |
| P1.25 | Add a work order / Send a message from the record | `RaiseFieldWork` door, `queue_account_message` | 14, 27, 28 | FLOW | **done** (2.531.0, §9.FLOW) — *Send a message* is the account's existing door |
| P1.26 | Documents from the move-in checklist (`ServiceRequestDocumentRequirement`, `move_in`) carried to the account at Complete (`BR-CUS-073`) | `services._move_in`, account documents | 25, 39 | IDN | **done** (2.528.0, §9.IDN-2 — every request document, by reference; wizard-only uploads are P2.25's) |
| P1.27 | Unit and meter status proved, not written: unit Occupied on activation and Vacant on cancel (`BR-MET-036`); a meter fitted by the visit In stock → Installed only when Work accepts the meter-set visit (`BR-AST-020`); sub-meters and devices linked to the account | tests only + `metering` seams read | 48, 24 | FLOW → WIZ-UNIT | **done** — unit Occupied/Vacant proved (2.531.0, P1.22 and P1.17 tests); the meter half `DEF-AST-9712` fixed in 2.538.0 by lane WIZ-UNIT: accepting a move-in visit raised for a meter still In stock installs it (`install_fitted_asset`) |
| P1.28 | The API contract written into this file (§9, appended) before any screen lane starts: field names fixed, every new key listed | this file | all | LIST | **done** (§9.LIST) |
| P1.29 | Law-14 proof: every catch-and-continue on these paths run on PostgreSQL (`config.settings.pgtest`) | tests | — | each lane | open — **MONEY part done** (2.529.0): `test_cr171_p1_29_money_pg.py` 4 passed on PostgreSQL 16; the savepoint proved load-bearing (removed → `InFailedSqlTransaction`) · **FLOW's half done** (2.531.0) — reopen, cancel and record-door suites green on PostgreSQL 16; the work-order cancel loop runs each call in a SAVEPOINT |
| P1.30 | Human-review ledger rows for every 🔒 file of P1, written before review | `12-governance/09-human-review-ledger.md` | — | MONEY | **done** (2.529.0) — three ledger rows; the three new 🔒 files went on `human_owned.txt` by PO ruling 2026-10-05 (a) *"Add them to the list."* (`DEF-GOV-9744`; lane RULINGS) |

### P2 — screens (40 tasks)

| # | Task | Files | Images | Lane | Status |
|---|---|---|---|---|---|
| P2.01 | Move-ins list header, five tiles, search, Filter panel + chips, columns, icons, pager | `MoveInsTab.tsx`, `AccountsListPage.tsx` (header only) | 01, 02 | LIST-UI | **done** (2.536.0, §14) |
| P2.02 | List row icons with tooltips and screen-reader names including the reference; no wrap on Reference | `MoveInsTab.tsx`, `parkedDrafts.tsx` | 01 | LIST-UI | **done** (2.536.0, §14) |
| P2.03 | List tests rewritten for S3/S4 (no footnotes, request and completed rows) | `MoveInsTab.test.tsx` | 01 | LIST-UI | **done** (2.536.0, §14) |
| P2.04 | Details header: back link, title + reference, chips, where line, actions by status (§0 table), More ▾ | `MoveRecordPage.tsx`, `moveRecordActions.ts`, `moveRecordActionBar.tsx` | 03–17 | DETAIL | **done** (2.534.0, §13) — `moveDetail/MoveInDetail.tsx`; the buttons are `moveInActionSlots` |
| P2.05 | Request Overview: tiles, *Request* and *Who* grids | `MoveRecordPage.tsx` (+ `moveDetail/RequestOverview.tsx`) | 03 | DETAIL | **done** (2.534.0, §13) |
| P2.06 | Approve, Decline, Ask for more modals (EFFECT line; required text; Escape / Cancel / outside closes) | `moveDetail/MoveRequestModals.tsx` | 18–20 | DETAIL | **done** (2.534.0, §13) — `FormModal` + `ConsequenceBox`; Decline danger |
| P2.07 | Request Documents, Messages, Audit tabs | `moveDetail/*Tab.tsx` | 21–23 | DETAIL | **done** (2.534.0, §13) — request *+ Send a message* held disabled (no request door, §9.REQ) |
| P2.08 | Move-in Overview: tiles that open tabs, *Details* grid, *Still open* | `moveDetail/MoveOverview.tsx` | 09–17 | DETAIL | **done** (2.534.0, §13) — *Still open* has no *Next* column (not served) |
| P2.09 | Unit & reads tab (unit grid, reads tree) | `moveDetail/UnitReadsTab.tsx` | 24 | DETAIL | **done** (2.534.0, §13) |
| P2.10 | Account tab (holder, co-owners, documents + Add document) | `moveDetail/AccountTab.tsx` | 25 | DETAIL | **done** (2.534.0, §13) — `co_owners` read added; documents = `AccountDocumentsTab` |
| P2.11 | Billing tab (tiles, plan and preferences with the plan link, fees, payment and deposit) | `moveDetail/BillingTab.tsx` | 26 | DETAIL | **done** (2.534.0, §13) — `fee_lines` read added; no *Base charge* tile, no *Taxable* column (§13) |
| P2.12 | Work, Messages, Audit (All/Changes/Messages) tabs | `moveDetail/*Tab.tsx` | 27–29 | DETAIL | **done** (2.534.0, §13) — the move-in Audit has no All/Changes/Messages filter: `DEF-CUS-9722` |
| P2.13 | Change move-in date, Enter opening read, Cancel move-in (with J6's four lines), Discard draft, Print modals/doors | `moveDetail/MoveActionsModals.tsx` | 10, 12–16 | DETAIL | **done** (2.534.0, §13) — Cancel follows the preview's own `allowed`/refusal and lists the refund it serves (`OQ-CUS-12790` ruled (a), server pending); Print is the browser's |
| P2.14 | Record tests rewritten for S1 (no two doors), every status's actions | `MoveRecordPage.test.tsx` | 03–17 | DETAIL | **done** (2.534.0, §13) — `moveDetail/MoveInDetail.dom.test.tsx` (23 cases, red-proved); the old file still pins the MOVE-OUT page |
| P2.15 | **Split the wizard first**: `MoveInWizard.tsx` keeps the frame, state and park; each step moves into its own file so four lanes can work without sharing one | `MoveInWizard.tsx` → `moveInWizard/Step{Unit,Customer,Billing,Review}.tsx` | 30–47 | WIZ | **done** (2.532.0) — one file per step plus `moveInWizard/moveInWizardContext.ts`, the one object every step reads; a step's NEW state goes in its own `useStep<X>Own()` hook (payload, park, hydrate), so an R2b lane never edits `MoveInWizard.tsx`. The old bodies moved whole: step 1 = old Unit + Which services + Start & read, step 3 = old Preferences + Deposit. P1.02/P1.03's three-part hold landed in the same commit; `DEF-CUS-9703` fixed |
| P2.16 | Move-in completed screen (`DEF-CUS-9702`) | `moveInWizard/MoveInCompleted.tsx` | 48 | WIZ | **done** (2.535.0) — `what_happened.items` drawn as `CheckList` ✓ rows, a row only for a key the commit reported; MVI number, *From request SR-…*, three doors. **Differences from the drawing, recorded:** opening reads show a COUNT (the answer's posted reads carry no unit, hard rule 3); the plan and the customer number are text (no plan link is served, no customer page exists); the server's remaining TRUE warnings still list under the panel. Retired keys: `customers.moveIn.done.*`, `.kicker`, `.carryWhy` **After-walk (2.540.2, `538ddb54b`):** `DEF-CUS-9730` fixed (the unit read *Occupied → Occupied* after a finished tenancy) and zero-count rows no longer drawn; photographs `08-qa/movein-2026-10-05/after/wizard/` (8, at 1440) by `10-scripts/cr171_move_in_wizard_walkthrough.mjs` |
| P2.17 | Frame: title *New move-in* / *Edit move-in · MVI-…*, Save draft & exit top right, four-step rail, Park / Back / Continue; the two ruled-out sentences removed and the third reworded (S9) | `MoveInWizard.tsx`, `moveShared.tsx` | 30, 47 | WIZ | **done** (2.533.0) — title *New move-in* / *Edit move-in · MVI-…* (a resumed draft, by its reference), *Save draft & exit* in the head (the frame's own `Save & exit` off), tick on a done step, Park left · Back · Continue right; kicker, step line, audit sentence and park age removed (S9); *"Occupied units aren't listed."* in eleven catalogues. The back link on `/move-ins/new` is *← Move-ins* whatever unit is picked. **Not done here:** the Edit door that OPENS a move-in for edit from the details view is P2.34 (WIZ-REV) |
| P2.18 | Step Unit: vacant unit select, unit header card, four groups | `StepUnit.tsx` | 30 | WIZ-UNIT | **done** (2.542.0) — image 30's *Unit* box: the picker with the unit card and Building · Unit · Owner · History inside it (`MoveInUnitPick` takes the card as children); §15 |
| P2.19 | Step Unit: move-in date panel | `StepUnit.tsx` | 30 | WIZ-UNIT | **done** (2.542.0) — its own *Move-in date* box, *Rates and reads use this date.* |
| P2.20 | Step Unit: Services and meters table (Start, tree, opening read + unit, expand facts, below-last-read) | `StepUnit.tsx`, `MoveInReadingsTable.tsx`, `moveReadsCapture.tsx` | 30–32 | WIZ-UNIT | **done** (2.542.0) — *Services and meters* as the kit's `TableArray`: Start tick per service, the meter tree (sub-meter and device nested), Size by NAME, reads as, last read, the opening read with its unit (required unless a visit is booked), ▸ facts (image 31), *Below the last read.* from `…/check` (image 32); `MoveInReadingsTable` stays the move-out's and transfer's |
| P2.21 | Step Unit: Field visit table — one searchable *Work order* | `features/work/FieldVisitOrders.tsx` | 30 | WIZ-UNIT | **done** (2.542.0) — `FieldVisitOrders layout="panel"`: # · Work order* (template, searchable) · For · Priority · Due · Window · Assign to (best-fit advice) · Note; *Visit needed*; *Raised when you complete* |
| P2.22 | Step Customer: Person / Company, type + sub-type, person fields | `StepCustomer.tsx`, `CustomerFields.tsx` | 33 | WIZ-CUST | **done** (2.543.0, §16) — `CustomerTypeFields` lifted out of `CustomerFields` (New account unchanged) so type + sub-type sit side by side; person fields as drawn, *Contact by* to the contact |
| P2.23 | Step Customer: Identity panel + Search customer ID + the result states — Existing customer, Possible match (name + date of birth only), No customer found; NO *only the name matches* state (PO ruling 2026-10-05, §9.IDN) | `StepCustomer.tsx`, `customerMatch/CustomerMatchPanel.tsx` | 33–37 | WIZ-CUST | **done** (2.543.0, §16) — `customerMatch/CustomerMatchPanel.tsx`: Existing customer · Possible match (Q5, as the amended §9.IDN) · New customer · Linked; no *Only the name matches.* |
| P2.24 | Co-owners / Owners and officers: tick + collapsible cards (one component, two kinds) | `components/` or `customers/CoOwnerCards.tsx` (built AS a component, rule 43) | 33, 38, 40 | WIZ-CUST | **done** (2.543.0, §16) — `CoOwnerCards.tsx` (one component, two kinds); the photo ID after Complete: `POST /accounts/{id}/co-owners/{coOwnerId}/photo-id` + `CoOwnerPhotoIdUpload` mounted on the details view's Account tab |
| P2.25 | Documents table array (checklist rows locked, a listed type drops out of the next row) | `StepCustomer.tsx`, `components/documents` | 33, 39 | WIZ-CUST | **done** (2.540.0 server, 2.543.0 screen, §16) — `MoveInDocumentsTable.tsx`; wizard uploads staged (`POST /move-ins/documents`) and filed at Complete (`documents`); the drawn Note column not built (no home) |
| P2.26 | Mailing address tick + card (built like co-owners) | `StepCustomer.tsx`, `UsAddressFields` | 33, 39, 40 | WIZ-CUST | **done** (2.543.0, §16) — `TickPanel` + the kit's `Disclosure` card and `UsAddressFields` |
| P2.27 | Company: legal name … registered in, Contact person, Bills go to + PO | `StepCustomer.tsx`, `CustomerFields.tsx` | 40 | WIZ-CUST | **done** (2.543.0, §16) — company facts, Contact person, Bills go to + PO, Owners and officers |
| P2.28 | Step Billing: Plan summary line + See full rates (shared plan-sections, narrowed) with the plan link | `StepBilling.tsx`, `UnitPricingPanel.tsx`, `planSections/PlanSections.tsx` (consumed, not forked) | 41, 42 | WIZ-BILL | **done** (2.545.0, §16) — `moveInWizard/MoveInPlanPanel.tsx`: Plan · Version on · Base charge · Deposit rule, *See full rates* = the shared `PlanSections` (one optional prop, `serviceExtra`, draws the unit's meter → sub-meter → device tree inside each service); `DEF-RAT-9738` and `DEF-RAT-9740` fixed |
| P2.29 | Preferences, Discounts, Tax — each a tick that opens a section of dropdowns / table array / date pickers + certificate upload | `StepBilling.tsx`, `moveInRequestBlocks.tsx`, `PortalLanguageField.tsx` | 41, 44 | WIZ-BILL | **done** (2.545.0, §16) — `moveInWizard/BillingExtras.tsx`: three ticked sections; *Autopay from* held with its reason (`DEF-CUS-9739`) |
| P2.30 | Fees table array (plan rows locked, *+ Add fee* type-to-search, Total) 🔒 display of money | `StepBilling.tsx`, `moveInWizard/FeesTable.tsx` | 41, 43 | WIZ-BILL | **done** (2.545.0, §16) — `moveInWizard/FeesTable.tsx` on the kit's `TableArray`; no *Taxable* column (`OQ-BIL-12788` (a)) |
| P2.31 | Payment: Pay now / Add to bill, method fields, part-payment line | `StepBilling.tsx`, `moveInWizard/MoveInPayment.tsx` | 41, 43, 44 | WIZ-BILL | **done** (2.545.0, §16) — `moveInWizard/MoveInPayment.tsx`; J4 worked case asserted and committed through the screen |
| P2.32 | Step Review: four sections with ✎ Edit to their step | `StepReview.tsx` | 45 | WIZ-REV | **done** (2.544.0, lane MVI-WIZ-REV record) — Unit · Customer · Billing as the kit's `Panel` + `FactBlock` `rows`, each ✎ Edit to its step; read from the other steps' PAYLOADS by contract key |
| P2.33 | Messaging table array (defaults untickable, + Add message) | `StepReview.tsx`, `MoveInMessages.tsx` | 45, 46 | WIZ-REV | **done** (2.544.0) — `TableArray`; defaults drawn as facts (Complete takes no choice for one); added rows are `extra_messages`; new read `GET /move-ins/message-templates` |
| P2.34 | Edit mode: the Add form filled, titled *Edit move-in · …*, for To approve, Waiting on customer, Not started, Draft | `MoveInWizard.tsx` | 47 | WIZ-REV | **done** (2.544.0) — `edit=1` read by `moveInWizard/useMoveInEdit.ts`; a request saves back through `PUT …/move-in-form` (no second draft — `DEF-CUS-9731` fixed); Not started resumes the request's park and is titled by its `MVI-`; Draft was already a resume (P2.17) |
| P2.35 | Wizard dom tests per step file; the seven-step tests re-pointed | `moveInWizard/*.dom.test.tsx` | 30–47 | each WIZ lane | open · WIZ-UNIT's share **done** (2.542.0) — `moveInWizard/StepUnit.dom.test.tsx` (13); 8 step-1 cases of `MoveInWizard.test.tsx` and 5 of `MoveEntryPoints.dom.test.tsx` re-pointed · **WIZ-REV share done** (2.544.0): `StepReview.dom.test.tsx`, `useMoveInEdit.dom.test.tsx`; review cases of `MoveInWizard.test.tsx` re-pointed |
| P2.36 | English catalogue keys per screen through `10-scripts/i18n_fanin.py`; retired keys (the ruled-out sentences, the result panel) through the same tool | `07-frontend/src/i18n/locales/en.json` | — | each lane | open · WIZ-UNIT's share **done** (2.542.0) — 80 keys added, 18 retired, 1 reworded (`DEF-CUS-9734`), through `i18n_fanin.py` · **WIZ-REV share done** (2.544.0): 86 keys, 4 retired |
| P2.37 | Eleven catalogues, written in their own language (B14 rule 35) | 11 locale files | — | I18N | **done** (2.547.0, §17 · lane MVI-I18N) — NATIVE-REVIEW-OWED |
| P2.38 | Route: `/moves/:ref` serves SR- references; the request page's *Open in Move-ins* door for a move-in request (hold-expiry test in the same commit, law 2) | `App.tsx`, `ServiceRequestDetailPage.tsx` | 03 | DETAIL | **done** (2.534.0, §13) — *Open in Move-ins →* on a move-in request; address held by `MoveInDetail.dom.test.tsx` |
| P2.39 | `route-b-migrated.txt` lists every new file (rule 21 per-file clause) | `07-frontend/src/styles/route-b-migrated.txt` | — | each lane | open · WIZ-UNIT's share **done** — no new screen file (StepUnit, FieldVisitOrders, the kit files were already listed) · **WIZ-REV share done** (2.544.0): `useMoveInEdit.ts` |
| P2.40 | Screen-component map rows for the new components | `04-docs/02-decisions/13a-screen-component-map.md` | — | WIZ | **done** (no version — a document) — the S19 row names the four step files, the context seam and `MoveInCompleted`; the details view's rows are DETAIL's |

### P3 — proof (8 tasks)

| # | Task | Status |
|---|---|---|
| P3.01 | Break every new guard first and quote the red (law 7), through the harness that runs it | **done** (§17, lane MVI-PROOF) |
| P3.02 | Photograph all 48 states at 1440 into `08-qa/movein-2026-10-05/after/` and diff each beside its image; every difference fixed or recorded | **done** (§17; contact sheet `08-qa/movein-2026-10-05/contact-sheet.html`, photos `after/p3/`) |
| P3.03 | Golden tests unchanged (`06-backend/tests/golden/`, G64 sentence printed); the first-bill tests unmodified | **done** (§17: 25 passed, 1 xfailed; G64 printed) |
| P3.04 | PostgreSQL proof of Complete, Cancel and Change date (law 14) | **done** (§17: 74 passed, 0 skipped on PostgreSQL 16) |
| P3.05 | `10-scripts/move_in_nineteen.sh` re-pointed to four steps and green; the beta counted before and after (read only) | **done** (§17: 19/19 + 2 meta; beta counts unchanged; 2.548.1) |
| P3.06 | Every suite and gate red line read and dated (law 7 habit 1) | **done** (§17 and the lane report) |
| P3.07 | Human review: each 🔒 file shown to the PO in plain English with its figure, ruling written verbatim | open — material prepared by lane MVI-PROOF (§17.1) for the coordinator |
| P3.08 | Versions recorded (CHANGELOG + version source), rollback statement re-checked | **done** (§17; §8.3 amended, `DEF-PAY-9760`) |

### P4 — end to end (30 tasks)

Seven move-ins (the PO's matrix, decision log *"THE END-TO-END SCOPE IS ACCEPTED AND WIDENED"*),
each run through the screens, then checked in the **database** and on the **Units, Assets,
Accounts, Payments, Route & Cycle, Work, Notifications and Billing** screens (plus Audit).

| # | Task | Status |
|---|---|---|
| P4.01 | Seed the starting data for M1–M7 on a fresh lane database (units with meter + sub-meter + device, a plan with deposit rules, fire's six sizes, a returning customer with two accounts and $84.20 outstanding, a church exempt, a school) | **done** — `10-scripts/cr171_e2e_matrix_world.py` (lane MVI-E2E-SEED, §17) |
| P4.02 | The matrix runner: one script, per case: submit through the browser, then a DB read-back and a screen walk of the eight modules, PASS/FAIL per check | **done for M1** — `10-scripts/cr171_e2e_matrix_run.mjs` + `cr171_e2e_matrix_readback.py`; M1 107 PASS · 7 FAIL, every FAIL a filed defect (§17). M2–M7 drivers are the R4 lanes' |
| P4.03–P4.05 | **M1** Residential · Single-family · person — Electric, Water, Sewer, Trash · new customer · field visit · pay by check: run · DB check · module screens | open |
| P4.06–P4.08 | **M2** Residential · Multi-family · person + co-owner — Water (meter + irrigation sub-meter + backflow device), Sewer · returning customer linked · add to bill | **run** (lane MVI-E2E-1, §19) — **104 PASS · 1 FAIL** on 2.549.0; the FAIL is `DEF-MET-9773` (a sub-meter's size makes the connection's size unresolved; the first bill cannot be priced) |
| P4.09–P4.11 | **M3** Residential · Senior/Low-income · person — Electric, Gas · assistance discount with evidence · part payment | **done** (lane MVI-E2E-1, §19) — **108 PASS · 0 FAIL** on 2.549.0 |
| P4.12–P4.14 | **M4** Commercial · Small commercial · company with owners — Electric, Water, Sewer, Trash, Storm water · Tax ID match · card | **run** (lane MVI-E2E-2, §21) — **115 PASS · 5 FAIL** on 2.549.0; FAILs: `DEF-BIL-9751` (with the PO) and `DEF-CUS-9776` ×4 (a company's account is named after its contact person) |
| P4.15–P4.17 | **M5** Commercial · Institutional & non-profit (church) — Water, Sewer, Fire (one 6" + two 2" lines) · tax exempt with certificate · **Fire $84.00 on one line** asserted | **run** (lane MVI-E2E-2, §21) — **101 PASS · 6 FAIL** on 2.549.0; **Fire $84.00 on ONE line PASS**; City tax removed, State + County kept (ruling (A)) PASS; FAILs: `DEF-BIL-9751`, `DEF-CUS-9776` ×3, `DEF-CUS-9774`, `DEF-CUS-9775` |
| P4.18–P4.20 | **M6** Industrial · Light industrial · company — Electric, Gas, Water, Solar (inverter behind the meter) · two work orders | **run** (lane MVI-E2E-3, §28) — **125 PASS · 3 FAIL** on 2.549.9; FAILs: `DEF-WRK-9784` (both visits refused, 0 orders), `DEF-CUS-9785` (raw code on Move-in completed), `DEF-BIL-9793` (first bill charges sewer the account never started) |
| P4.21–P4.23 | **M7** Government · Schools — Water, Sewer, Trash · government exemption · PO number on bills | **run** (lane MVI-E2E-3, §28) — **100 PASS · 4 FAIL** on 2.549.9, entered as **Municipal** because Government is not pickable (`DEF-CUS-9786`, root `DEF-CUS-9808`); GOVERNMENT certificate removes the City tax, County stays (PASS); FAILs: `DEF-CUS-9786`, `DEF-BIL-9787` (PO on no bill), `DEF-CUS-9788` ×2 (PO on no screen) |
| P4.24 | Cancel after Complete on a copy of M1: J6's four reversals seen in the DB and on screen; unit back to Vacant | **run** (lane MVI-E2E-3, §28) — **128 PASS · 4 FAIL** on 2.549.9; account closed the day before, agreements ended, WO-0053 canceled, reads kept, unit Vacant (PASS); FAILs all `DEF-CUS-9789` (no refund, no deposit release for money still processing) |
| P4.25 | Change date on a copy of M2; first-bill proration moves | **run** (lane MVI-E2E-3, §28) — M2 copy **121 PASS · 3 FAIL**, M1 copy **113 PASS · 3 FAIL** on 2.549.9; account, agreements and proration move (M2 base $24.00 → $20.13, M1 $48.00 → $40.26, PASS); FAILs all `DEF-CUS-9790` (details view and list keep the old date) |
| P4.26 | A request through To approve → Ask for more → Approve → Start → Complete; and one Declined | **done** (lane MVI-E2E-3, §28) — **32 PASS · 0 FAIL** on 2.549.9 |
| P4.27 | Units: occupied, account on the unit; Assets: each meter, sub-meter, device on the account with its opening read; a meter-set visit accepted moves In stock → Installed (`BR-AST-020`) || **read back in every case** (lane MVI-E2E-3, §28: unit Occupied/Vacant derived, each meter Installed with its opening read in its own unit, PV-M6 still behind E-M6); the meter-set acceptance is NOT exercised — no case sets a meter from stock — open for that half |
| P4.28 | Payments: deposit held, fees posted, receipt, a balanced pair for every amount (hard rule 5); Billing: first-bill preview with the fees, discounts and exemption | **read back in every case** (lane MVI-E2E-3, §28: fees, payments, receipts, audit, balanced journals with the not-yet-journaled count printed; first bill with fees, exemptions and taxes); deposit-not-billed-twice now PASS on 2.549.6+ — open only for `DEF-BIL-9793`, `DEF-BIL-9787`, `DEF-CUS-9789` |
| P4.29 | Route & Cycle: account in its route sequence and cycle, first bill date; Work: each order with its template on the technician's day; Notifications: each message queued on its channel | **read back in every case** (lane MVI-E2E-3, §28: route RT-006 walk order and cycle CY-001, work orders with template and technician's day, messages queued never sent) — open only for `DEF-WRK-9784` (no visit on an electric or gas meter) |
| P4.30 | Close: the closure bar (a person did each task on screen), the reporter told which build, rollback restated | open |

**Count: P0 6 · P1 30 · P2 40 · P3 8 · P4 30 = 114.**

### 8.1 · Rounds and lanes — at most five at once, never two on one screen file

| Round | Lanes (max 5) | Starts when |
|---|---|---|
| **R1a** | SCHEMA (P1.01 🔒 M), REQ (P1.06–P1.08), IDN (P1.09, P1.11 read side) | now — three lanes, because FIN-T and FIN-W are running |
| **R1b** | LIST (P1.02–P1.05, P1.28), MONEY (P1.12–P1.16, P1.30 🔒), FLOW (P1.17–P1.27; P1.19 after FIN-W), IDN (P1.10, P1.26) | P1.01 merged — every other lane codes against its schema; only SCHEMA writes a customers migration, so two migrations never race for one number |
| **R2a** | LIST-UI (P2.01–P2.03), DETAIL (P2.04–P2.14, P2.38), WIZ (P2.15–P2.17, P2.40) | P1.28 contract written |
| **R2b** | WIZ-UNIT (P2.18–P2.21), WIZ-CUST (P2.22–P2.27), WIZ-BILL (P2.28–P2.31), WIZ-REV (P2.32–P2.34), DETAIL continues | P2.15 split merged — each step lane owns one step file; `MoveInWizard.tsx` stays WIZ's. **Progress (lane WIZ, 2026-10-05): the split is PUSHED — `40e104b88`, 2.532.0. R2b may start.** Each lane owns `moveInWizard/Step<Unit|Customer|Billing|Review>.tsx`; new state goes in that file's `useStep<X>Own()` (its `payload`, `park`, `hydrate`), never in `MoveInWizard.tsx` — `moveInWizard/moveInWizardContext.ts` says how |
| **R3** | I18N (P2.37), PROOF (P3.01–P3.08) | R2 merged |
| **R4** | E2E-1 (M1–M3), E2E-2 (M4–M5), E2E-3 (M6–M7 + P4.24–P4.29) | R3 green |

**Shared files are serialised, not shared:** `services._move_in` is written by MONEY in R1b and the
other R1b lanes hand MONEY a function to call (named in §9); `MoveInWizard.tsx` is WIZ's alone;
`en.json` is written only through `i18n_fanin.py`; `FieldVisitOrders.tsx` is not touched until FIN-W
has landed and is then WIZ-UNIT's alone.

### 8.2 · Versions

P0 ships no product code and carries **no version**. Every later task takes its own number at push
time with `10-scripts/allocate.py version --bump change` (`--bump fix` for a fix-only push) and
`--verify`, records it in `CHANGELOG.md` and the version source of truth as the `CR-165`/`CR-166`
commits did, and appends its record to this file as a new section (§9 onward).

### 8.3 · Rollback

* **P0:** nothing to roll back (records only).
* **Screens (P2):** redeploy the previous build. No stored fact changes from a screen alone; parked
  drafts written by the four-step form keep every seven-step key (P1.03), so an older build can
  still resume them. ⚠ **RE-CHECKED BY P3.08 (lane MVI-PROOF, 2026-10-05): an older build resumes
  the seven-step VALUES only.** What the four steps added rides under `step_own` (co-owners, fees
  and payment, extra messages, staged documents) and an older build ignores it, so a draft parked on
  2.532.0 or later and resumed after a rollback has those to type again; nothing is lost from the
  park itself.
* **Migrations (P1.01, 🔒):** additive only — new tables, nullable columns, one widened check
  constraint. The down path drops the new tables and columns and narrows the constraint, and it
  **refuses** while any `move_in_jobs` row is `cancelled` or any fee line / co-owner / extra-message
  row exists (it names the count), because dropping them would delete records a clerk wrote.
* **Money (P1.12–P1.15, P1.22, 🔒):** payments, refunds, journal lines and issued bills written under
  the new code are immutable (hard rule 4) and are **not** reversed by a rollback; a rollback stops
  new ones. The first-bill extension (P1.14) is behind the move having fee lines: an account opened
  by the old wizard has none, so its first bill is unchanged either way.
* **Deposit releases (`OQ-CUS-12790` (a), 2.541.0, 🔒) — ADDED BY P3.08, 2026-10-05; this list named
  neither migration until then (`DEF-PAY-9760`).** `payments/0047` adds `deposit_releases` and
  `payments/0048` its RLS. A code rollback (redeploy) leaves both tables and every row untouched.
  **Do not migrate back past `payments/0047` while it holds a row:** its reverse is Django's plain
  drop and, unlike `customers/0080`, does NOT refuse — it would delete the record of a deposit
  released (say Nilesh's $150.00) while its DR 2300 / CR 2400 entry stays in the books.
  `DEF-PAY-9760` (open) gives it the refusing down path `0080` has.

---

## 9 · The API contract (P1.28 writes it here before any screen lane starts)

*Written by P1.28 (lane MVI-LIST): §9.LIST below is the list and details-view contract; §9.IDN, §9.REQ and §9.1 are the other R1 lanes' halves. Screen lanes code against these names.*

### 9.IDN · `POST /customers/match` with `purpose: "search_customer_id"` (lane MVI-IDN, P1.09 + P1.11 read side, 2.522.0)

**Built:** `06-backend/apps/customers/owner_lookup.py` (`search`, `customer_accounts`, `company_facts`).
**Tests:** `06-backend/tests/test_cr171_p109_search_customer_id.py` (16 cases: 15 on any database + 1 PostgreSQL proof).
No migration, no new route, nothing written.

**Request** — the same body New Connection sends, plus one key:

```
POST /api/{tenant}/customers/match
{ "kind": "person"|"company", "name", "date_of_birth", "ssn", "driving_licence", "phone", "tax_id",
  "purpose": "search_customer_id" }
```

Without `purpose` the answer is unchanged: `{"verdict", "candidates"}` under PO ruling Q5
(New Connection calls it while the clerk types and must not pay for a ledger read per key).

**Response** — the Q5 keys, plus `search`:

```
"search": {
  "result": "found" | "possible" | "new" | null,   // null = nothing to judge (no kind, or a name only)
  "count": <every customer our rule shows>,         // `customers` is cut at 5, found first
  "customers": [{
    "id", "customer_no", "display_name", "kind",
    "verdict": "found" | "possible",               // Q5's match / possible — NOTHING else (2026-10-05)
    "tier": "strong" | "weak",                      // identity_match.tier_for — NOT the verdict; never drawn as one
    "agreed": ["name","date_of_birth","ssn",...],
    "basis": "matched on name, date of birth and Social Security number",
    "ssn_last4", "driving_licence_last4", "tax_id_last4",          // BR-CUS-092: last four only
    "accounts": {
      "count": <every linked account>,
      "rows": [{ "id", "account_no", "status_code", "status_name", "closed_at",
                 "address": {"line1","unit_label","city","state","postal_code"} | null,
                 "balance",          // the ledger's signed position, 6-dp string
                 "outstanding",      // max(balance, 0)
                 "confident",        // false for a weak or untiered link
                 "held_with": [names] }],   // cut at 10, owed first
      "outstanding_total",           // Σ outstanding over CONFIDENT links, all accounts
      "unconfident_outstanding",     // Σ over weak/untiered links, left out of the total
      "currency", "basis", "available", "unavailable"
    },
    "company": null | { "legal_name",
                        "contact_person": {"full_name","email","phone","account_no"} | null,
                        "bills_go_to": {"line1","line2","city","state","postal_code","country","account_no"} | null }
  }]
}
```

⚖️ **AMENDED 2026-10-05 BY PO RULING — ONE MATCH RULE WITH NEW CONNECTION (lane RULINGS, `2.537.0`).**
Decision log *"FOUR PO RULINGS IN ONE REPLY"* (1), verbatim: *"if match based on our logic then we
say match if it is not then we dont say it"*. The search's verdicts are now New Connection's Q5
(`owner_lookup.verdict_for`, the one function both answers call); the two bullets struck below were
2.522.0's and are SUPERSEDED. **For lane MVI-WIZ-CUST (P2.23): the Customer step draws exactly two
verdicts — *Existing customer* (`found`) and *Possible match* (`possible`, a person's name AND date
of birth) — and a third state, *No customer found* (`new`). There is NO *"Only the name matches."*
line: image 35's is superseded and not built.** A customer our rule does not call a match is not in
`customers` at all, so there is nothing on the wire to draw it from.

**Rules as built (from `2.537.0`):**
* **found** = Q5's *match*: a person's SSN or driving licence, or a company's Tax ID, is the one on
  file (`identity_match.REUSE_ID_FIELDS`). Two customers both matching are both **found**, as New
  Connection lists them; the clerk picks one with *Use this customer*.
* **possible** = Q5's *possible*: a person's name AND date of birth both agree (a company has no
  date of birth, so a company is never *possible*). Advisory (`BR-CUS-019`).
* **not shown** = anything less — a name alone (Rosa typed with a different date of birth), a date
  of birth alone, a phone. Such a customer is neither in `customers` nor in `count`.
* **new** = nobody our rule shows.
* `tier` stays on each row because the commit's own link step applies the money test
  (`BR-CUS-089`) to it; it is NOT the verdict.
* ~~**found** = exactly one candidate passes the money test … Two sure matches → both
  **possible**.~~ ~~**possible** = every other customer `find_candidates` surfaces with at least
  one agreeing fact, a name-only hit included (image 35).~~ — 2.522.0, SUPERSEDED 2026-10-05.
* Money is `customer_statement`'s (ledger, `DEF-127`), never `accounts.balance`. Shown, never moved.
* Address walked to the premises through `seams.envelope_addresses` (hard rule 8).
* `company` is served only on a **found** company (its Tax ID is the one on file); `null` for a
  person. A company is never *possible* and never shown on a name alone.
* Tenant scoped: `find_candidates`, `customer_statement` and every read filter by tenant; RLS
  proved on PostgreSQL for `customers`, `customer_accounts`, `accounts`, `journal_lines`.
* **Proved:** red first on the tip (`KeyError: 'search'`); green on SQLite (15 + the 10 Q5 cases, 1 PostgreSQL case skipped by vendor) and on PostgreSQL 16 (26 passed, 0 skipped). The isolation cases were also shown red by deleting `find_candidates`' `tenant_id` filter (`assert 'found' == 'new'`; `['C-90001', 'C-50001'] == ['C-90001']`) and restored.

⚠ **SUPERSEDED 2026-10-05 BY §9.1 — THE NAMES BELOW ARE THIS LANE'S PROPOSALS, NOT THE COLUMNS.**
MVI-SCHEMA built `accounts.po_number` (not `bill_po_reference`) and `accounts.bills_go_to`, a
choice `account_holder` | `contact_person` (not a yes/no `bills_to_contact`); `customers.registered_in`
is text. Build to §9.1 and §9.IDN-2; the table stays only as the record of what was asked.

**P1.11 — fields with no home today (for MVI-SCHEMA, P1.01).** The read serves only what exists:
legal name (`customers.display_name`), the EIN as `tax_id_last4`, the contact person (the primary
`contacts` row of the company's newest account) and *bills go to* (that account's
`addresses kind='mailing'`). Image 40 also draws these, and **none has a column**:

| Field (image 40) | Proposed home | Note |
|---|---|---|
| Trading as | `customers.trading_as` text null | already in P1.01 |
| Business type | `customers.business_type` text null (LLC, corporation, partnership, sole proprietor…) | already in P1.01; a sole proprietor is `OQ-1242`, open |
| Registered in | `customers.registered_in` CHAR(2) null (US state / CA province) | already in P1.01 |
| PO or reference on bills | `accounts.bill_po_reference` text null | already in P1.01; per account (one company's two sites may carry two POs); billing READS it to print |
| Bills go to: *Same as the contact person* | `accounts.bills_to_contact` bool default true | already in P1.01; when false the bill goes to the `addresses kind='mailing'` row |
| Contact person: Job title | `contacts.job_title` text null | **NOT in P1.01's list — a new ask of MVI-SCHEMA** |
| Contact person: Contact by | `contacts.contact_by` text null (email · text · phone · letter) | **NOT in P1.01's list — a new ask**; the person form's *Contact by* (image 33) has the same gap |

The writes wait for P1.01 (round R1b); nothing here guesses a column.

### 9.IDN-2 · P1.10, P1.11 writes, P1.26 — what Complete writes besides the account (lane MVI-IDN, 2.528.0)

**Built:** `06-backend/apps/customers/move_in_people.py` (new); four small hunks in
`services.py` (`MOVE_IN_FIELDS` += four keys, `CONTACT_FIELDS` += `job_title`, `contact_by`,
`_validate_contact` validates them, `_move_in` pops the block before the transaction and calls
`move_in_people.write_at_complete` inside it, right after `_carry_request_custom_answers`).
Six refusal keys in all eleven catalogues (`i18n_fanin.py`). No migration (0080's columns).
**Tests:** `06-backend/tests/test_cr171_p110_move_in_people.py` (14 cases: 13 on any database + 1 PostgreSQL proof).

**The move-in payload gains (all optional):**

```
POST /units/{unit_id}/move-in   ·   POST /accounts/{id}/move-in
{ …,
  "contact": { "full_name", "email", "phone", …, "job_title", "contact_by" },   // contact person (image 40)
  "co_owners": [ { "full_name"*, "relationship", "title", "ownership_pct", "signs_for_company",
                   "personal_guarantee", "date_of_birth", "ssn", "driving_licence", "phone",
                   "email", "contact_by", "responsible_for_bills" } ],
  "company": { "trading_as", "business_type", "registered_in" },
  "po_number": "PO-7781",
  "bills_go_to": "account_holder" | "contact_person" }
```

**Answer gains** `"people": {"co_owners": n, "company_updated": [fields], "documents_carried": n}`
for P1.21's *What happened*. Identifiers never appear in it.

**Rules as built:**
* **The kind is the holder's, never the clerk's.** On a person's account every row is a
  `co_owner`; on a company's an `officer` (image 38 / 40). A sent officer-only field (`title`,
  `ownership_pct`, `signs_for_company`, `personal_guarantee`) on a co-owner, or `relationship` on
  an officer, is refused by field name. `ownership_pct` is percent points, 0–100, stored to six
  places (`50` → `50.000000`).
* SSN and licence through `co_owner_models.set_identifier` (ciphertext + blind index); the audit
  row `customers.account.co_owner_added` carries the **last four only** (BR-CUS-092).
* `company` is refused on a person (BR-CUS-1022). On a linked returning company only the fields
  the clerk typed overwrite; a blank is *not asked*, never *erase*. Before/after to `audit_log`.
* `bills_go_to = contact_person` with no contact on the account is refused (*Add the contact
  person first.*).
* **P1.26:** every document on the move's request whose `storage_ref` is a stored document of
  this tenant is filed on the new account **by reference** — the account card points at the
  same `StoredDocument`, nothing is re-uploaded or copied, the request keeps its card, and the
  uploader and upload time travel with it (BR-CUS-073, BR-CUS-080; CR-031 statement 6, *"all
  documents transfer"*). Folder: `kyc`. Skipped: a card with no file, a reference that is not a
  stored document (sample data's `sample-data://`, the fixtures' `s3://`), a file already filed.
* Every refusal is raised before the transaction (shape) or inside it (holder-dependent) and
  writes nothing: the account, the move record and every row here roll back together.

**Proved:** red first with `services.py` at the tip's bytes and the module present but uncalled —
13 failed: the new keys refused as `customers.account.unknown_field`, `KeyError: 'people'`, and
`{'bills_go_to', …, 'po_number'} <= frozenset(…)`. Green on SQLite (13 + 1 PostgreSQL case skipped by
vendor) and on PostgreSQL 16 (14 passed, 0 skipped: a refusal raised inside the commit leaves no
account and the connection still answers; `account_co_owners` hides Brazos Bend's row from Lone
Star Ridge under the RLS probe role). Neighbouring suites (move-in, contact edit, identity,
deposit, service subset, custom fields, Q5 lookup, 0080 schema; 18 files) — 286 passed; the 9
failures and 1 error there are red **on the tip without this change** too (re-run with
`services.py` at the tip's bytes: identical) and are already filed (`DEF-NOT-6267`, `DEF-2586`,
`DEF-CUS-6017`, `DEF-CUS-6018`) except one, now `DEF-MET-9710`.

**Not here, stated:** the co-owner's **photo ID** (`photo_id_document_id`) is not taken at
Complete — the account it is filed on does not exist until then; it is P2.24's upload onto the
Account tab after Complete. Documents uploaded on the **wizard itself** (image 39, no request) have
no home before Complete either; where they park is WIZ-CUST's (P2.25) and they need a carry like
this one.

**§9.IDN read side, widened (same version):** the search's `company` block now serves the 0080
columns — `trading_as`, `business_type`, `registered_in`, `po_number`, `bills_go_to` (the
choice), the contact's `job_title` and `contact_by` — and the mailing address moved to
`bills_go_to_address`. No screen read the old key yet (P2.23 is not built).

### 9.REQ · A move-in REQUEST on the details view — its buttons, its Messages and Audit tabs, and Edit through the Add form (lane MVI-REQ, P1.06 · P1.07 · P1.08, 2.524.0)

**Built:** `06-backend/apps/customers/move_in_request.py` (new: the status words and buttons for a
request row, the Edit form's field map and save), `service_request_service.resend_the_ask`,
`service_request_reads.timeline_queryset` / `history_row` / `message_source_ids` / `message_row`
(`history_tab` now reads through them, same output), `service_request_api.py` (four routes),
`customers/notifications_seam.request_messages` → `notifications/selectors.deliveries_for_sources` /
`source_delivery_row` (notifications' own published read), `tenancy/wizard_parks.CARRIED_REFERENCE_KEYS`
(+ `request_no`).
**Tests:** `06-backend/tests/test_cr171_move_in_request_view.py` (20 cases; green on SQLite and on
PostgreSQL 16). **No migration, no new column, no schema ask.**

#### Statuses and buttons (one function — LIST's P1.04/P1.05 call it, never a second copy)

`move_in_request.request_status(state)` and `move_in_request.request_actions(state)`:

| Request `state` | `status` | `actions`, in the drawn order (primary, secondary, then More) |
|---|---|---|
| `submitted`, `under_review` | `to_approve` | `approve` · `ask_for_more` · `edit` · `decline` |
| `more_info` | `waiting_on_customer` | `approve` · `resend_ask` · `edit` · `decline` |
| `refused` | `declined` | `reopen` (`OQ-CUS-12789` → (a), built by MVI-FLOW in 2.527.0) |
| anything else | `null` (not a request row on the list) | `()` |

Whether a submitted request appears on the Move-ins list at all (resolver suggests *served,
vacant*) is P1.04's rule (§6.1), not this function's.

#### The doors each action calls — every one existed before this CR except `resend-ask`

| Action (image) | Door | Body the modal sends | Answer |
|---|---|---|---|
| Approve ✓ (18) | `POST /service-requests/{id}/approve` | `{"outcome": "move_in"}` | detail + `job` (`raised`: the pending `move_in_jobs` row — *Not started*; or `not_raised` with its code). No account opens (`BR-CUS-1077`). A blocking condition (`BR-CUS-1095`'s four, arrears, fee) answers 422 `BIZ-COMPLETENESS` naming it — show it IN the modal. |
| Decline… (19) | `POST /service-requests/{id}/refuse` | `{"reason": T, "reason_code": "other", "message_to_applicant": T}` where T is the one required *Reason* text | detail + `applicant_message` (`state` `queued` / `not_sent`, `reason`) |
| Ask for more… (20) | `POST /service-requests/{id}/transitions` | `{"action": "request_info", "reason": T, "message_to_applicant": T}` where T is *What you need* | detail + `applicant_message` |
| Resend the ask (05) | **`POST /service-requests/{id}/resend-ask`** (new) | none — the words are the stored ask's, never the caller's | detail + `applicant_message`; 422 `BIZ-STATE` `transitionNotAllowed` (`action: resend_ask`) unless `more_info` |
| Edit (04, 06) | **`GET` / `PUT /service-requests/{id}/move-in-form`** (new) | see below | see below |
| Reopen (08) | **`POST /service-requests/{id}/reopen`** (new, MVI-FLOW 2.527.0) | `{"reason": T}` — REQUIRED (`BR-CUS-072`) | detail; `header.state` = `submitted` (*To approve*), same `request_no`; 422 `VAL-REQUIRED` on a blank reason; 422 `BIZ-STATE` `transitionNotAllowed` unless `refused`, `reopenNotAMoveIn` for a refused request that is not a move-in. ~~HELD on `OQ-CUS-12789`~~ — closed → (a) 2026-10-05. |

**J2 — what `refuse` actually requires, checked in code and asserted by a test
(`test_the_refuse_door_needs_a_reason_and_does_not_need_a_code`):** `reason` is REQUIRED (blank →
422 `VAL-REQUIRED`, `REASON_REQUIRED`); `reason_code` is OPTIONAL (absent → stored NULL, nothing
refused); a code outside the five (`service_request.REFUSAL_REASONS`) → 422 `VAL-UNKNOWN-LOOKUP`;
`message_to_applicant` is the letter's body and is optional (absent → no letter, `not_sent`). **So
the server does NOT need a code** — J2's *"where the server needs a code"* never arises. The move-in
Decline modal sends `other` anyway, so every move-in decline is filed under a countable value
rather than NULL (decision log 2026-10-05, MVI-REQ (2)). The one text is both the register's
`reason` and the letter: the modal's EFFECT line is *The customer is told.*

#### Messages tab (image 22) — `GET /service-requests/{id}/messages?page=&per=`

Paged in SQL, newest first, standard envelope `{count, next, previous, results}`. Every letter
queued to the applicant for THIS request: the acknowledgement (keyed on the request) and each
refusal / ask / resend / approval letter (keyed on its timeline row). Row:

```
{ "id", "template_code",            // the MESSAGE — the catalogue names it, no prose travels
  "to_name", "to_address",          // the envelope's name and where it went
  "channel", "status",              // the queue's own word: never print "sent" for "queued" (BR-NOT-013)
  "queued_at", "sent_at" }
```

`unavailable: "notifications_publishes_no_message_read"` (and an empty page) only if notifications
publishes no read. *+ Send a message* (image 22) is not a request door yet — it is P1.25's
(`queue_account_message` is account-scoped and a request has no account).

#### Audit tab (image 23) — `GET /service-requests/{id}/audit?page=&per=&f.kind=all|changes|messages`

Paged in SQL, newest first. Rows are `history_tab`'s shape: `{id, at, actor, actor_name,
actor_kind (staff|customer|system), kind (state|note|system…), from_state, to_state, note,
note_type, internal}`. WHO is `actor_name` (never the id, B14 rule 31); WHAT is composed by the
catalogue from `kind` / `to_state` / `note_type`. `f.kind=messages` keeps rows whose `note_type`
starts `applicant_message:` or `acknowledgement:`; `changes` is the rest; anything else reads as
`all` and is echoed back as `kind`.

#### Edit uses the Add form (J3, image 47) — `GET|PUT /service-requests/{id}/move-in-form`

**GET** →

```
{ "request": {"id", "request_no", "state", "status", "editable"},   // editable: Draft/Submitted/Under review/More info
  "park_id": <uuid>|null,  "step": <int, 1 when nothing parked>,
  "values": { ...the parked rest..., overlaid with the request's own facts:
     "service_request_id", "unit_id" (resolved_unit_id), "opened_at" (requested_start),
     "services": [codes],
     "customer": { "full_name", "email", "phone", "dob", "customer_kind" ("person"|"company"),
                   "account_type" (code), "account_subtype" (id), "mailing_same",
                   "mailing_line1/line2/city/state/postal_code",
                   "ssn": "", "driving_licence": "" },          // NEVER served back (BR-CUS-092)
     "preferences": { "preferred_language" } } }
```

The value keys are the move-in wizard's existing ones (`unit_id`, `opened_at`, `customer`,
`preferences`, `deposit`, `reads`, `discount`, `services`, `field_visit`, `service_request_id`), so
the four-step form reads them as it reads a resumed draft.

**PUT** `{ "step": n, "values": {…} }` — *Save draft & exit*. In ONE transaction:
1. the request's own fields (the table below) are written back through the request's writers —
   `update_request` (capture fields), `set_customer_category`, `set_services` (each service keeps the
   start it already had) — only those that changed;
2. everything else is parked in ONE `wizard_parks` row, flow `move_in`, `waiting_on: ""` (a draft),
   `subject_ref: {service_request_id, request_no, unit_id}`, reference = the request's own
   `SR-…` number (no `MVI-` number is spent). A second save updates the same row.
3. Nothing is approved; the state does not move; no job is raised.

Answers the same shape as GET. Refused (422/409, the existing `terminalNoEdit` / `approvedNoEdit`)
once the request is decided, and nothing is parked. A request field the writer refuses (a bad date
of birth) rolls the park back too.

| Form value | Request column (writer) |
|---|---|
| `customer.full_name` / `email` / `phone` / `dob` | `applicant_name` / `applicant_email` / `applicant_phone` / `date_of_birth` |
| `customer.ssn` / `driving_licence` | `ssn` / `drivers_licence` — written only when typed; empty = unchanged |
| `customer.customer_kind` | `applicant_kind` (`company` ↔ `business`) |
| `customer.mailing_same`, `mailing_*` | `billing_address_same`, `billing_*_as_given` |
| `customer.account_type`, `account_subtype` | `account_type`, `account_subtype` (`set_customer_category`) |
| `opened_at` | `requested_start` |
| `unit_id` | `picked_unit_id` → `resolved_unit_id` (only when changed) |
| `services` | `service_request_services` (`set_services`) |
| `preferences.preferred_language` | `preferred_language` |

⚠ **For LIST (P1.04):** a `move_in` park whose `subject_ref.service_request_id` names a request
that is still a request row IS that request's edit — it must NOT be listed as a separate *Draft*
row. **For WIZ / DETAIL (P2.34, Start):** when the request is approved and the clerk presses *Start*,
the wizard should resume this park (`GET /wizard-parks?flow=move_in`, match on
`subject_ref.service_request_id`) so the parked rest is not lost; its reference stays the `SR-`
number while the job carries the `MVI-` number.
### 9.LIST · The Move-ins list and the details view — every status, one function (lane MVI-LIST, P1.02 · P1.03 · P1.04 · P1.05 · P1.28)

**Built:** `06-backend/apps/customers/move_in_list.py` (new — the status model, the five-arm SQL
union, the tiles, the rows), `move_reads.py` (the four-step list and the seven→four map;
`move_ins_list` forwards to `move_in_list`), `move_record_reads.py` (`SR-` references, `redesign()`
adding the new keys to every state), `seams.latest_read_dates_for_units` →
`metering.selectors.latest_read_dates_for_units` (new, set-wise), `api.py` (`GET /move-ins` takes
`f.status` and `f.service`), front end `moveShared.tsx` (`MOVE_IN_SEVEN_STEP_TO_FOUR`,
`moveInStoredStep` — inert until P2.15) and `wizardPark.ts` (`storedStep(stored, row)`).
**Tests:** `tests/test_cr171_p1_04_move_ins_list.py`, `tests/test_cr171_p1_05_move_record_view.py`,
`tests/test_def_648_step_count_parity.py` (amended), `moveInStoredStep.test.ts`.
**No migration. Nothing is written by anything in this section.**

#### The eight statuses (CR §6.1, as built) — `move_in_list.STATUSES`

| `status` | Row (`row_kind`) | Rule | Row icon (`action`) |
|---|---|---|---|
| `to_approve` | `request` — `service_requests` `submitted`/`under_review` whose resolution `service_request.suggests_move_in` (FLOW's one predicate — §9.FLOW), outcome not another flow's | REQ's `move_in_request.request_status` (one function) | `review` |
| `waiting_on_customer` | `request` — the same, `more_info` | ″ | `review` |
| `declined` | `request` — the same, `refused`. A Reopen (lane FLOW, `OQ-CUS-12789` (a)) moves the state back to `submitted`, and the status follows: nothing here stores a status | ″ | `view` |
| `not_started` | `pending_job` — `move_in_jobs.pending` with no draft; `account` — a legacy BR-CUS-018 draft account with no move-in record | `BR-CUS-1077` | `start` |
| `draft` | `parked_move_in` — an unlinked `move_in` draft; **or** `pending_job` whose request a draft names (the row then carries `park_id`) | `BR-SHL-048` | `resume` |
| `waiting_on_a_read` | `move_record` — a committed move-in on an OPEN account whose unit has a meter with no committed read on/after `effective_on` | `move_reads.unit_reads_cell` | `view` |
| `completed` | `move_record` — every other (incl. a unit with no meters, and any whose account has closed) | | `view` |
| `cancelled` | `pending_job` in state `cancelled`; `move_record` whose account closed before the day it opened — `move_in_cancel.is_cancelled`, FLOW's one predicate (`DEF-CUS-9713`, fixed 2.531.1) | S2 | `view` |

⚠ **A cancelled COMMITTED move-in is read by `move_in_cancel.is_cancelled`** (the account closed
the day before it opened — §9.FLOW's cancel). This section first named a `close_reason` value the
database refuses and nothing writes; that was `DEF-CUS-9713`, fixed in 2.531.1.

⚠ **A draft for a request is not its own row.** A `move_in` draft whose `service_request_id` (in
`subject_ref` — REQ's Edit door — or in `values` — the seven-step wizard) names a request that is
still a `request` row, or the request of a pending job, is hidden; the request/job is the row.

#### `GET /move-ins?q=&page=&per=&sort=&dir=&f.status=&f.service=` (images 01, 02)

* `f.status` — a GROUP or one status. Groups (image 02's radio): `all` (no filter) · `to_approve`
  = to_approve + waiting_on_customer · `open` = not_started + draft + waiting_on_a_read ·
  `completed` · `closed` = declined + cancelled (not drawn; under *All*). Any other single status
  name selects that status. An unknown value selects NOTHING (BR-SHL-011). ⚠ `to_approve` as a
  filter is the group.
* `f.service` — comma-separated service codes (`water,sewer`); a row matches if it takes ANY.
  Requests and jobs: the request's `service_request_services`; drafts: `values.services` (a draft
  with no ticks yet is not matched); accounts and committed move-ins: the account's agreements.
* `f.state` — the seven-step screen's old filter, still honoured on the old three kinds until
  P2.01 replaces the screen; request and committed rows answer none for it.
* `sort` ∈ `created` (default, `desc`) · `move_in_date` · `account`. Every sort ends in `id`.
* `q` (≥ the tenant's minimum): customer/applicant name · request `SR-` · move `MVI-` (job,
  draft reference, record) · account number · unit/address (metering's own match).

**Response** — the old envelope, plus:

```
{ "rows": [Row], "total", "page", "per", "pages", "sort", "dir", "sorts",
  "statuses": [8 names], "status_groups": {"to_approve": [...], "open": [...], "completed": [...], "closed": [...]},
  "filters": ["status", "service", "state"],
  "search": {"hint": "Search customer, unit, MVI…", "min_chars", "legs", "unavailable"},
  "kpis": { "to_approve", "not_started", "drafts", "starting_this_week", "waiting_on_a_read",
            "by_status": {status: n},          // all eight, the whole list
            "reads_unjudged", "reads_unwired", "starting_basis",
            ...the old keys (open, waiting_on, waiting_on_a_reading, oldest…) until P2.01 },
  "exclusion", "states", "columns", "as_of" }
```

Tiles count the WHOLE list (never the page, never the search). `starting_this_week` = move-in
date within today … today + 7 over the `to_approve` + `open` statuses (a draft carries no date
the database can read, so it is not counted — stated in `starting_basis`).

**Row** — every kind carries every key the old rows carried (`move_no`, `row_kind`, `account_no`,
`customer`, `unit`, `move_in_date`, `step`, `deposit`, `state`…), plus:

```
"status":    one of the eight,
"reference": "SR-26-0014" | "MVI-26-0011" | null,   // what the row links to: /moves/{reference}
"action":    "review" | "start" | "resume" | "view",
"services":  ["water", "sewer"] | null,               // null = a draft that has not ticked yet
"opening_read": { "state": "taken"|"due"|null, "meters_total", "meters_read",
                  "missing": ["E-5041"], "readings": [{"register", "reading", "unit"}],
                  "unavailable": {code, br_ref, detail} | null },   // committed rows only; others: no_opening_read_before_complete
"step": { "reached": 3|null, "of": 4, "id": "billing"|null, "name": "Billing"|null,
          "unavailable", "done": true (committed rows only) },
request rows also: "request_id", "request": {id, request_no, state, requested_start}, "actions": [REQ's buttons]
committed rows also: "record_id", "request_id"
a job reading `draft` also: "park_id"
```

#### `GET /moves/{ref}` (images 03–17) — `ref` may now be an `SR-` number

Resolution order: committed move (`MVI-`) → **request** (`SR-`: a request row answers the request
view; an approved one answers its job or its committed move-in) → draft reference → job (`MVI-`).
The request comes before the draft because REQ's Edit draft carries the request's own `SR-`.

Every state keeps every key it had and gains: `status` (the list's, for the same reference —
asserted), `reference`, `actions`, `step` (four-step cell on a draft), `tiles`, `facts`,
`tab_counts`, `still_open`.

* **Request** (`state: "request"`): `actions` = REQ's table (`approve · ask_for_more · edit ·
  decline` / `approve · resend_ask · edit · decline` / `reopen` — §9.FLOW), `chips`
  `{requested_on, moves_in_on}`, `tiles` `{move_in_date {value, basis:"requested"}, services
  {count, codes}, documents {attached, outstanding}, unit {vacant, unit_label}}`, `facts.request`
  `{request_no, channel, submitted_on, move_in_date, unit {id,label,line}, building {id,
  premise_no, address}, unit_is_vacant, services, plan, customer_type}`, `facts.who` `{kind,
  name, matched {id, customer_no, name} | null, matched_absence {code: no_existing_customer |
  not_searched}, email, phone, mailing_same, mailing}`, `tab_counts {documents, messages, audit}`.
* **Job / draft / committed**: `tiles` `{opening_reads {taken, of, recorded_on, unavailable},
  fees {total, currency, lines, paid: null, paid_unavailable (P1.13)}, work_orders {raised,
  open}, messages {count: null, unavailable (P1.25)}}`, `facts.details` `{move_no, from_request,
  moved_in_on, customer, account, plan, unit, building, services, from_account,
  earliest_legal_start, committed_by}`, `tab_counts {work, messages: null}`, `still_open`
  `[{kind: "work_order", order} | {kind: "opening_read", register}]`. A job reading `draft`
  carries `park_id`.

#### P1.02 / P1.03 — the step

`move_reads.MOVE_IN_STEP_IDS = ("unit","customer","billing","review")`, `MOVE_IN_STEP_COUNT = 4`.
A draft's step is mapped seven→four (`{1:1, 2:1, 3:2, 4:1, 5:3, 6:3, 7:4}`) unless the draft was
written by the four-step form: **WIZ (P2.15) must write `values.step_shape = "four"` on every
park**, flip `moveShared.MOVE_IN_STEPS` to the four ids above, and pass `moveInStoredStep` as the
`move_in` `storedStep` in `parkedDrafts.WIZARD_PARK_FLOW_SURFACE` — two tests go red until all of
that lands together (`test_def_648`'s strict xfail; `moveInStoredStep.test.ts`'s HOLD case). Every
value in a seven-step draft is kept: only the step moves.

*P1.28 writes the endpoint contract. The field names below are P1.01's and are fixed: every
later lane codes against them.*

### 9.1 · P1.01 — the schema (lane MVI-SCHEMA, migration `customers/0080_cr171_p1_01_move_in_redesign`, 🔒)

**New table `account_co_owners`** — model `apps.customers.co_owner_models.AccountCoOwner`
(`account.co_owners` is the reverse name). RLS ENABLE + FORCE.

| Field | Type | Notes |
|---|---|---|
| `id` | uuid7 | |
| `tenant_id` | FK tenants | |
| `account_id` | FK accounts, NOT NULL | written at Complete (P1.10); before that the parked wizard holds them |
| `kind` | text, CHECK | `co_owner` \| `officer` (`KINDS`) |
| `full_name` | text, NOT NULL | |
| `relationship` | text NULL | co-owner (*Spouse*) |
| `title` | text NULL | officer only (*Managing member*) — CHECK refuses it on a co-owner |
| `ownership_pct` | numeric(18,6) NULL, 0–100 | officer only, percent points (`50.000000`) |
| `signs_for_company` · `personal_guarantee` | bool, default false | officer only (CHECK) |
| `date_of_birth` | date NULL | |
| `ssn` · `driving_licence` | encrypted text NULL | contexts `account_co_owners.ssn` / `account_co_owners.driving_licence`; write ONLY through `co_owner_models.set_identifier(row, field, value)`, which also writes `ssn_bidx` / `driving_licence_bidx`; read the last four with `crypto.last_four` (BR-CUS-092) |
| `phone` | text NULL | not encrypted (follows `contacts`; never match evidence) |
| `email` | citext NULL | |
| `contact_by` | text NULL, CHECK | `email` \| `text` \| `phone` \| `letter` (`CONTACT_BY`) |
| `photo_id_document_id` | FK account_documents NULL | the photo ID is a filing card on the same account; NULL = *No ID* |
| `responsible_for_bills` | bool, default false | *Also responsible for the bills* |
| `is_sample` · `created_at` · `updated_at` | | |

**New table `move_fee_lines`** — model `apps.customers.move_in_extras.MoveFeeLine`
(`move_record.fee_lines`). RLS ENABLE + FORCE.

| Field | Type | Notes |
|---|---|---|
| `move_record_id` | FK move_records, NOT NULL | written at Complete (P1.12) |
| `seq` | smallint | unique per move |
| `kind` | text, CHECK | `deposit` \| `fee` (`FEE_KINDS`) — the deposit is told apart by KIND |
| `source` | text, CHECK | `plan` \| `charge_code` (`FEE_SOURCES`) — image 41's *From* |
| `charge_code_id` | uuid NULL, no FK | rating `charges` row priced (BR-BIL-007) |
| `code` · `description` | text · text NULL | as quoted on the day (*DEPOSIT*) |
| `amount` | numeric(18,4), ≥ 0 | |
| `currency` | char(3), default `USD` | |
| `note` | text NULL | |
| `is_sample` · `created_at` | | |

No `taxable` column — `OQ-BIL-12788` was open when this was written and is now CLOSED (a): never taxed at move-in, so there is nothing to record (§9.MONEY). No pay-now/add-to-bill column — the money is a
payment (J4, P1.13).

**New table `move_extra_messages`** — model `apps.customers.move_in_extras.MoveExtraMessage`
(`move_record.extra_messages`). RLS ENABLE + FORCE. The two defaults are NOT rows here.

| Field | Type | Notes |
|---|---|---|
| `move_record_id` | FK move_records, NOT NULL | |
| `seq` | smallint | unique per move |
| `template_key` | text | the notification template chosen |
| `recipient` | text, CHECK | `customer` \| `co_owner` \| `unit_owner` |
| `co_owner_id` | FK account_co_owners NULL | required when `recipient = co_owner`, refused otherwise (CHECK) |
| `channel` | text, CHECK | `email` \| `text` \| `letter` \| `portal` |
| `send_when` | text, CHECK | `on_complete` \| `day_before_move_in` \| `on_move_in_date` \| `day_before_visit` |
| `notification_id` | uuid NULL, no FK | the queued outbound row; written by P1.20 |
| `is_sample` · `created_at` | | |

**New columns on existing tables (all nullable, nothing back-filled):**

| Table | Column | Notes |
|---|---|---|
| `customers` | `trading_as` · `business_type` · `registered_in` | free text; `registered_in` is a state code (*IA*); vocabularies are P1.11/P2.27's |
| `accounts` | `po_number` | *PO or reference on bills*; the commercial bill template's existing `po_number` token |
| `accounts` | `bills_go_to` | CHECK `account_holder` \| `contact_person` (`models.BILLS_GO_TO`); NULL = account holder |
| `accounts` | `autopay_instrument_id` | uuid, no FK → `payments.stored_payment_instruments` (*Autopay from*, §6); the writer (P1.15) validates it; `autopay` stays the on/off |
| `contacts` | `job_title` | *Job title* of a company's contact person (image 40) — lane MVI-IDN's ask (§9.IDN) |
| `contacts` | `contact_by` | CHECK `email` \| `text` \| `phone` \| `letter` (`models.CONTACT_BY`, shared with `account_co_owners`) — images 33, 40; lane MVI-IDN's ask |
| `move_in_jobs` | `state` | CHECK widened: `pending` \| `done` \| `cancelled` (`move_in_jobs.STATE_CANCELLED`, written by P1.22) |

**Reused, no column added:** the exemption TYPE and ISSUED date are
`rating.TaxExemptionCertificate.category` and `.issued_on` (with `certificate_ref`, `expires_on`);
the certificate file is an `account_documents` row (P1.15). The contact person is a `contacts`
row (E59).

**§9.IDN's proposed names, reconciled:** `accounts.bill_po_reference` is **`accounts.po_number`**
(the commercial bill template's existing token, one spelling); the bool `bills_to_contact` is
**`accounts.bills_go_to`** (`contact_person` = IDN's `true`; `account_holder` or NULL = `false`,
the bill going to the holder's `addresses kind='mailing'` row as IDN describes);
`customers.registered_in` is text, not `CHAR(2)` (it holds the two-letter code either way).
IDN's two new asks, `contacts.job_title` and `contacts.contact_by`, are ADDED (rows above).

**Down path:** reversing 0080 refuses, naming each count, while any co-owner, fee line, extra
message, `cancelled` job, or value in the eight new columns exists (§8.3).

## 10 · P1.01 record (lane MVI-SCHEMA, 2026-10-05) — version **2.526.0**

* **Built:** `customers/0080_cr171_p1_01_move_in_redesign` 🔒 (ledger row) — the fields are §9.1.
  New modules `apps/customers/co_owner_models.py` and `apps/customers/move_in_extras.py`, both
  registered at the foot of `models.py`; `move_in_jobs.py` §3 amended (S2: `cancelled` now has a
  writer — `P1.22`).
* **Proved on PostgreSQL 16 (`sbh_wmschema`):** up → down → up, with `pg_class` showing ENABLE +
  FORCE on the three tables after each up and nothing after the down; the CHECK reading
  `pending, done, cancelled` / `pending, done`. A down with one company row holding *trading as*
  **refused**: *"customers/0080 will not reverse: it would delete 1 company names (trading as /
  business type / registered in) (customers)"*, and the migration stayed applied.
* **Tests:** `tests/test_cr171_p1_01_move_in_schema.py` (SQLite and PostgreSQL) and
  `tests/test_cr171_p1_01_rls_pg.py` (PostgreSQL). Red first on the base tip `f43fbdffe`: 25
  failed, 1 passed (before the two `contacts` cases were added) — the one that passed asserts the tax-exemption REUSE, which was already true.
* **Also built, at lane MVI-IDN's ask:** `contacts.job_title` and `contacts.contact_by` (§9.1).
* **Rollback:** reverse `customers/0080`; it refuses while a clerk's record would be lost (§8.3).

## 11 · Lane MVI-FLOW record (R1b, 2026-10-05) — the contract its screens call (§9.FLOW)

### 9.FLOW · Reopen a declined move-in request — `2.527.0`

`OQ-CUS-12789` CLOSED → (a), PO verbatim: *"Reopen: SR-26-0014 goes back to "To approve". Same number, her documents stay, and the decline stays in its history."*

| | |
|---|---|
| Door | `POST /api/{tenant}/service-requests/{id}/reopen` · `AdminOrClerk` |
| Body | `{"reason": "Lease received."}` — **required** (`BR-CUS-072`: *"REOPENING REQUIRES A REASON"*) |
| Answer | the request detail; `header.state` = `submitted` → `move_in_request.request_status` = `to_approve` |
| Refusals | blank reason → 422 `VAL-REQUIRED` `customers.serviceRequest.reasonRequired`; not `refused` → 422 `BIZ-STATE` `customers.serviceRequest.transitionNotAllowed`; refused but not a move-in (`service_request.suggests_move_in` false) → 422 `BIZ-STATE` `customers.serviceRequest.reopenNotAMoveIn` (*"Only a move-in request reopens."*, eleven languages) |
| Writes | the SAME row: `state` → `submitted`; `outcome`, `reason_code`, `decision_reason`, `refusal_message`, `decided_at`, `decided_by`, `closed_at` lifted to empty (their values into `audit_log` `service_request.reopened` `before`); one NEW `service_request_events` state row `refused → submitted` carrying the reason. The refused row and its reason are untouched. Documents, services, answers, fee lines: untouched. No money moves; no letter is queued. |
| Buttons | `move_in_request.request_actions("refused")` = `("reopen",)` — image 08's *More ▾ Reopen*. The modal asks one required *Reason* (our judgment; decision log). |
| For LIST (P1.04) | `service_request.suggests_move_in(resolution_kind)` is THE predicate for "this request is a move-in" (§6.1) — call it, do not write a second. |

## 12 · Lane MVI-MONEY record (R1b, 2026-10-05) — version **2.529.0**

### 9.MONEY · Fees, Pay now / Add to bill, the first bill, Billing-step extras, *See full rates* (lane MVI-MONEY, P1.12–P1.16 · P1.29 · P1.30, 2.529.0)

**Built:** `06-backend/apps/customers/move_fees.py` 🔒 (fee rows, the commit's lines, the payment),
`apps/customers/move_in_preferences.py` 🔒 (autopay source, discount claims, tax exemption),
`apps/customers/move_in_money_api.py` (three reads), `apps/rating/move_in_fees.py` 🔒 (prices and
the narrowed sections), `apps/billing/first_bill.py` 🔒 (`move_in_fee_lines`; `DEF-BIL-9709`),
`apps/rating/plan_reads.py` (`DEF-RAT-9708`), `services._move_in` (pops and calls),
`apps/assets/selectors.py` (`parent_asset_id` on the asset-on-unit row). **No migration.**
**Tax: none, anywhere — `OQ-BIL-12788` CLOSED (a).** Every fee row and line carries
`taxed_at_move_in: false`; no code's `taxable_default` is forwarded.

#### Reads (before the account exists)

```
GET /move-ins/fees?unit_id=&account_type=&services=water,sewer&size_class=
→ { unit_id, account_type, services, currency,
    total,                                // Σ rows WITH a figure, 4-place string
    deposit: <GET /accounts/deposit-standard's own answer, whole>,
    rows: [ { kind: "deposit", source: "plan", code: "DEPOSIT", name: "Security deposit",
              amount, locked: true, refusal: null|"size_required", taxed_at_move_in: false },
            { kind: "fee", source: "plan", locked: true, charge_id, code, name, service,
              charge_type: "one_time", amount_rule, gl_account_id,
              amount: "25.0000"|null,
              priced_by: "flat"|"size"|"per_case"|"percent", size_class,
              refusal: null|"size_not_recorded"|"size_not_priced"|"no_price"|"percent_has_no_basis",
              taxed_at_move_in: false } ] }

GET /move-ins/fees/quote?unit_id=&account_type=&code=RUSH&services=
→ one row as above with source "charge_code", locked false; refusal also
  "unknown_code" | "not_a_one_time_code" | "not_for_this_class"

GET /move-ins/pricing?unit_id=&account_type=&services=&size_class=
→ { unit_id, account_type, services, plan_absent: null|"unit_has_no_plan",
    plan: <GET /plans/{id} sections, NARROWED> + narrowed_to {customer_class, services, sizes},
    deposit, fees: {rows, total, currency},
    assets: [ { service, assets: [ { asset_no, type, qualifier, size_class, children: [...] } ] } ],
    move_in_fees_taxed: false }
```
Narrowing (rating, never recomputed): services → the ticked ones; each `base.by_size` /
`minimum.by_size` → this connection's recorded size (all rows when none recorded) and this class or
every class; `charge_codes` → those reaching the class; `taxes` → those reaching the class, each
`move_in_fees_taxed: false`. Unit prices read at up to four places (`DEF-RAT-9708`).
`services` absent = every service the unit carries. Missing `unit_id`/`account_type` → 422 naming each.

#### The commit — new keys on `POST /accounts/{id}/move-in` and `POST /units/{id}/move-in`

```
"fees": [ { "kind": "deposit"|"fee", "source": "plan"|"charge_code", "code", "amount", "note" } ],
"payment": { "mode": "pay_now"|"add_to_bill", "method_code", "amount", "confirmation",
             "received_on", "cleared_on", "idempotency_reference" },
"autopay_instrument_id": <payments instrument `ref`>,     // needs "autopay": true
"discount_claims": [ { "discount_id", "note" } ],
"tax_exemption": { "category_id", "certificate_ref", "issued_on", "expires_on",
                   "certificate": { "name", "content_type", "content_base64" } }
```
All five are optional; a payload without them is the old move-in, byte for byte (no fee lines, no
`fees`/`payment`/`billing_extras` keys in the answer). The deposit DECISION still travels in
`deposit` (`required` with `take_now: false` is the new form's normal answer — the money is
`payment`'s). **Refused, nothing written:** a fee figure not the code's (`customers.moveFees.amountNotCode`,
params `code`, `amount`), a code that is not a one-time code for this class (`codeRefused`, `reason`),
a `source: plan` code the plan does not name (`notFromPlan`), a code twice (`duplicateCode`), a
`per_case` code with no amount (`amountRequired`), a deposit row where none is owed
(`customers.deposit.take_without_deposit`) or not the plan's figure (`customers.deposit.amountNotPlan`),
no mode (`customers.movePayment.modeRequired`), more than the fees (`moreThanFees`, `total`),
Pay now beside `deposit.take_now` (`depositTakenTwice`), an instrument not this customer's
(`customers.moveIn.instrumentRefused`), a source with autopay off (`autopayOff`), a discount the plan
does not carry (`discountNotOffered`) or claimed twice (`discountTwice`), an unreadable certificate
(`certificateUnreadable`).

**Answer additions** (beside the account):
```
"fees":    { lines: [ { seq, kind, source, charge_code_id, code, description, amount, currency,
                        note, taxed_at_move_in: false } ], total, currency },
"payment": { mode, total, currency, amount_paid, on_first_bill,            // image 43's sentence
             payments: [ { purpose: "deposit"|"prepay", amount, payment_id, payment_no, status } ],
             receipt_no, notes: [...] },
"billing_extras": { autopay: {instrument_id, brand, last_four},
                    discounts: [ { discount_id, status: "pending"|"not_required" } ],
                    tax_exemption: { status: "recorded"|null, certificate, document } }   // null = no category sent
// ⚖️ 2.539.0 (lane RULINGS): "held_for_system_admin" is GONE from both. PO ruling 2026-10-05 (b),
// verbatim: "Let billing clerks record it themselves. - we have set the limits so clark can do it -
// its a day to day work". Rating's enrol_account and record_exemption_certificate admit a Billing
// Clerk; the claim is enrolled (pending when the programme asks for proof) and the certificate is
// rating's row at once. Nothing is parked on eligibility_claimed. A refusal from rating now refuses
// the move-in by name. Worked: Marcus records a church's certificate against a 2.00% city tax ->
// $0.00 of that tax on a $100.00 bill (an account without one pays $2.00). The Plans & Rates
// certificate door (POST /exemption-categories/{id}/certificates) stays System Admin's (A4).
```
`deposit` (the existing block) is updated when Pay now takes it: `notes` loses
`deposit_deferred_to_first_bill`, gains the payment number and `held_after`.

**First bill (P1.14):** the deposit line is unchanged (plan − paid; none when waived —
`DEF-BIL-9709`); the move's FEE lines replace the default `CONN`; each is kind `fee`,
`taxable: false`, with its `charge_id`; a code with no GL refuses at draft. Worked (J4): $150.00 +
$25.00 + $40.00 = $215.00 of one-time lines; $100.00 paid today is a prepay credit applied at issue.
**Proved:** SQLite 45 cases across `test_cr171_p1_12_move_in_fees.py`, `…p1_14_first_bill_fees.py`,
`…p1_15_move_in_preferences.py`, `…p1_16_move_in_pricing.py`; PostgreSQL 16 `test_cr171_p1_29_money_pg.py`
(4 passed; the savepoint in `move_in_preferences._held` proved load-bearing — removed, case 3 fails `psycopg.errors.InFailedSqlTransaction`). ⚖️ **2.539.0: `_held` and its savepoint are DELETED with the refusal they caught** (PO ruling (b)); PostgreSQL 16 re-run: case 1 proves the clerk's enrolment and certificate commit with the move-in, case 3 proves a refusal from rating rolls the whole move-in back with the connection still answering — 15 passed, 0 skipped. `test_us_bil_010_first_bill.py` unmodified and green; golden tests unchanged.
### 9.FLOW · The committed move-in's doors — `2.531.0`

All take the move NUMBER (`MVI-…`, case-insensitive) in the path, never a uuid (B14 rule 31). Module `apps/customers/move_in_flow_api.py`, included from `config/urls.py`. `AdminOrClerk`.

| Door | Body | Answer | Refusals |
|---|---|---|---|
| `GET /moves/{ref}/cancel-preview` | — | `{kind: "not_started"\|"committed", move_no, allowed, refusal: null\|{code, message_key, question?, deposit_held?}, reverses}`; `reverses` = `{job: "cancelled"}` for a job, or `{account: {account_no, closes_on}, refund: {amount (4dp) \| null, currency}, work_orders: [order_no], reads_kept: n, unit_after: "vacant"}` | 404 unknown ref |
| `POST /moves/{ref}/cancel` 🔒 | `{note?, refund_method?: "check"\|"ach"}` (default `check`) | not started: `{kind, move_no, status: "cancelled", job: {state, closed_reason}}`; committed: `{kind, move_no, status: "cancelled", account: {account_no, status, closed_at}, agreements_ended, refund: null \| {refund_id, amount, currency, method, status: "requested"}, work_orders_cancelled: [order_no], reads_kept, unit: "vacant", warnings: [{code: "work_orders_not_cancelled", order_no}]}` | `customers.moveIn.cancel.alreadyCancelled` · `.notCancellable` · `.accountNotLive` · `.billIssued` · `.billingUnreadable` (422 BIZ-STATE); ~~a held deposit → `refusal.code = move_in_cancel_deposit_held` … `NotImplementedError("OQ-CUS-12790")`~~ **SUPERSEDED 2.541.0 (lane RULINGS, `OQ-CUS-12790` (a)):** a held deposit no longer refuses. The preview's `reverses.refund` gains `deposit_released` (4dp) and its `amount` is the ONE refund the press raises — today's credit PLUS the deposit (Nilesh: `"175.0000"`, of which `"150.0000"` released); the answer gains `deposit_released: null \| {amount, currency, release_id}`. A register deposit that payments does not hold refuses the whole cancel (`PaymentRuleError`, BR-PAY-012) and writes nothing. |
| `POST /moves/{ref}/move-in-date` | `{opened_at: "YYYY-MM-DD"}` | `{move_no, opened_at, was, agreements_moved, visits_to_reschedule: [order_no]}` | `customers.moveIn.date.invalid` (422 VAL) · `.date.billIssued` · `customers.moveIn.cancel.billingUnreadable` · `customers.account.start_on_prior_move_day` (BR-CUS-056) · `customers.moveIn.notStartedYet` (a job) · `.cancel.alreadyCancelled` |
| `POST /moves/{ref}/opening-reads` | `{reads: [{meter_no, value \| estimate: true, channel?, read_at?}]}` — `read_at` defaults to the account's `opened_at` | `{move_no, posted_reads, warnings: [{row_no, meter_no, rules}]}` (metering's) | metering's named-row refusal (BR-MET-129); `customers.event_reads.rows_required` |
| `POST /moves/{ref}/work-orders` → 201 | the wizard's *Field visit* answer `{template_ids?, orders?: [{type_id, priority_id?, due_on?, crew_id? \| technician_id?, note?}]}` | `{move_no, work_orders: [...], warnings}` | `customers.moveIn.work.nothingToRaise` (422 VAL); nothing raised → Work's own `work.fromFlows.notRaised` (422) |
| *Send a message* | — | **no new door**: `GET\|POST /accounts/{account_id}/communication` (ACC-S16); the record serves `account_id` | — |

**For LIST (P1.04 / P1.05), three things to call rather than re-derive:**
* `move_in_cancel.is_cancelled(account)` — a committed move-in is **Cancelled** when `account.closed_at < account.opened_at`. A job is Cancelled when `move_in_jobs.state = cancelled`. ⚠ **`DEF-CUS-9713`:** LIST's 2.530.0 `move_in_list` keys this on `close_reason = 'move_in_cancelled'`, which `ck_accounts_close_reason` forbids and nothing writes — LIST to switch to this predicate.
* *Moved in on* / the list's move-in date for a committed move-in is **`accounts.opened_at`**, not `move_records.effective_on` (the record is never updated; *Change move-in date* moves the account).
* `service_request.suggests_move_in(resolution_kind)` — is this request a move-in (§6.1).

### 9.FLOW (continued) · Step 1's reads and Complete's additions — `2.531.0`

| Door | Body | Answer |
|---|---|---|
| `GET /units/{id}/move-in-facts` (P1.17) | — | `{unit: {id, unit_no, label, unit_type, floor_label, square_feet, is_common_area, occupancy: "vacant"\|"occupied", address: {line1, city, state, postal_code}}, building: {premise_no, name, premises_type, premises_type_name, inside_city_limits, area_code, area_name, parcel, parcel_verified, routes: [{code, name, service, cycle_code, cycle_name}]}, owner: null \| {name, account_no, status_name, billed_while_vacant}, history: {first_occupant, previous: null \| {account_no, name, closed_at}, plan_changes: int \| null}}` — a cancelled move-in never counts as an occupant; `plan_changes: null` = rating cannot say, never 0 |
| `GET /units/{id}/move-in-meters` (P1.18) | — | `{unit_id, services: [{service, start: true, metered, meters: [ROW]}], unplaced: [ROW], counts: {services, meters, devices, opening_reads_needed}, assets_readable}`; ROW = `{asset_no, kind: "meter"\|"sub_meter"\|"behind_the_meter", type_name, location_note, size_class, reads_as: null \| {multiplier (6dp), digits}, unit, last_read: null \| {value, unit, read_at, channel}, needs_opening_read, last_test_date, test_interval_months, children: [ROW]}` — sub-meters and devices nest under their meter (BR-AST-003) |
| `POST /units/{id}/move-in-meters/check` (P1.18, image 32) | `{reads: [{meter_no, value}]}` | `{rows: [{meter_no, value, last_value, unit, below_last_read: true\|false\|null}]}` — `null` when there is nothing to compare; advice only, metering still decides at commit |
| Complete (`POST /units/{id}/move-in`, `POST /accounts/{id}/move-in`) — new key in (P1.20) | `extra_messages: [{template_key, recipient: "customer"\|"co_owner"\|"unit_owner", co_owner_name? (required for co_owner — a co-owner written by the same Complete), channel: "email"\|"text"\|"letter"\|"portal", send_when: "on_complete"\|"day_before_move_in"\|"on_move_in_date"\|"day_before_visit"}]` — the two defaults are NOT rows (naming one → `customers.moveIn.messages.defaultTwice`) | |
| Complete — new keys out (P1.20, P1.21) | | `extra_messages: [{seq, template_key, recipient, channel, send_when, state: "queued"\|"planned", not_queued: null \| "scheduled_send_not_queued_at_complete" \| "recipient_has_no_message_door" \| "template_wording_not_published" \| "notifications_refused"}]` (never `sent`, BR-NOT-013) · `request_no` (`SR-…` or null) · `what_happened: {move_no, request_no, items: [{key, …}]}` with keys `customer` · `account` · `services` · `opening_reads` · `unit` (`{now, was}`) · `co_owners` · `documents` · `work_orders` (`{count, declined, orders: [{order_no, assignee}]}`) · `fees` · `payment` · `deposit` · `messages` (`{queued, planned}`) — a key the commit did not report is ABSENT, never zero. **For MONEY:** `fees` / `payment` / `deposit` appear in `what_happened` as soon as `_move_in`'s result carries those keys. |

`DEF-CUS-9702`: `plan_snapshot_not_recorded` is no longer served on a move-in; `deposit_carry_forward_unavailable` stays (it is true — nothing carries a deposit at move-in) and its sentence is now the fact alone, *"No deposit was carried forward."*, in eleven languages. ⚠ `customers.moveIn.carryWhy` (the wizard's own copy, P2) still states the expired reason; P2.16/P2.31 retire it.


## 13 · Lane MVI-DETAIL record (R2a, 2026-10-05) — version **2.534.0**

**Built (P2.04–P2.14, P2.38):** `07-frontend/src/features/customers/moveDetail/` — `MoveInDetail.tsx`
(the frame: head, buttons, More ▾, tabs, modal host), `RequestOverview.tsx`, `MoveOverview.tsx`,
`DocumentsTab.tsx`, `MessagesTab.tsx`, `AuditTab.tsx`, `UnitReadsTab.tsx`, `AccountTab.tsx`,
`BillingTab.tsx`, `WorkTab.tsx`, `MoveRequestModals.tsx`, `MoveActionsModals.tsx`,
`moveDetailParts.tsx`, `moveDetailEndpoints.ts`; `moveRecordActions.moveInActionSlots` (the buttons by
status); `MoveRecordPage.tsx` renders `MoveInDetail` for every move-in status and keeps its own page
for a move-OUT; `ServiceRequestDetailPage.tsx` gains *Open in Move-ins →* on a move-in request.
Server: `move_record_reads.redesign` serves two READ-ONLY keys, `fee_lines` and `co_owners`
(no identifier, BR-CUS-092). 238 catalogue keys in all eleven (`i18n_fanin.py`). Judgments: decision
log 2026-10-05 *"MOVE-IN REDESIGN P2.04–P2.14 + P2.38"*.

### 9.DETAIL · what the details view calls, and the one parameter it hands the wizard

| Act | Door |
|---|---|
| Approve ✓ / Decline… / Ask for more… / Resend the ask / Reopen | §9.REQ, §9.FLOW, as written (Decline sends `reason_code: "other"`) |
| Start (Not started) | `/move-ins/new?request=<request id>` — the wizard's existing door |
| **Edit (a request, or Not started)** | **`/move-ins/new?request=<request id>&edit=1`** — ⚠ **for WIZ-REV (P2.34): `edit=1` is the one parameter this screen sends; read it to open the Add form in edit mode** (GET/PUT `move-in-form`, §9.REQ). Until P2.34 lands the form opens prefilled from the request. |
| Edit (Draft) | `resumePath({id: park_id, flow: "move_in"})` |
| Change move-in date · Enter opening read · Cancel move-in… · Add a work order | §9.FLOW (`move-in-date`, `opening-reads` by METER number, `cancel-preview` + `cancel`, `work-orders` with Work's `FieldVisitOrders` payload) |
| Discard draft… | the wizard park's own discard door |
| Send a message | `AccountCommunicationDialog` (`/accounts/{id}/communication`) |
| Print | the browser's |
| Messages tab (move-in) | `GET /outbound?f.account_id=` · Audit tab (move-in) `GET /audit-log?f.entity_id=<account>` · Billing *Paid* `GET /payments?f.account_id=` |

### What differs from images 03–29, and why (each recorded, none silently dropped)

| Image | Drawn | Built | Why |
|---|---|---|---|
| 03–17 | Chips *Asked …*, *Approved …*, *Declined …*, *Cancelled …*, *Visit 8:00–12:00* | Requested / Moves in / Step n of 4 / Moved in only | those dates are not served on `GET /moves/{ref}`; not invented |
| 09–17 | *Still open* has a *Next* column (who · when) | Item · State | not served on `still_open` |
| 09–17 | Messages tile *2 sent* | *N queued* | the queue's word (BR-NOT-013) |
| 22 | *+ Send a message* on a request | drawn, disabled with its reason | no request door (§9.REQ) |
| 24 | ID cells link to the asset | plain numbers | the meters read serves no asset id |
| 25 | *+ Add document* over a 4-column table | the account's own Documents tab (*Upload document*) | rule 43 — reused, not re-drawn |
| 25 | Matched · Contact by · SSN · Driver's license in the holder grid | not drawn | not served on the account read; identifiers never shown whole |
| 26 | *Base charge* tile; *Taxable* column; *First bill* fact | not drawn | base not served on the record; `OQ-BIL-12788` (a) — nothing is taxed at move-in; first bill date not served |
| 27 | 7-column work table + *+ Add work order* | Work's `WorkOrdersTab` (account host), whose *Raise work here* is the add door; the move's own *Add a work order* (§9.FLOW) is in More ▾ while a read is due | rule 43 — not wrapped, or Work's band and raise door would draw twice |
| 29 | *All · Changes · Messages* | unfiltered, paged | `DEF-CUS-9722` (no read by kind) |
| all | panels white on grey, tiles boxed | the kit's `Panel` and `KPIStrip` | rule 44 — our standard decides the look |

**Proved:** `moveDetail/MoveInDetail.dom.test.tsx` 23 cases (every status's head and More ▾,
danger tier, S1's two doors gone, the three modals' bodies, Cancel held while the preview refuses, opening
reads by meter number, Start/Edit addresses, the request door's address) — red first by breaking the
completed menu, Decline's tier and the cancel hold (3 red), then green; `tests/test_cr171_p2_detail_reads.py`
3 cases — red first (`fee_lines` emptied, an `ssn_last4` added), then green; `moveRecordActions.test.ts`,
`routeBUtilities.test.ts`, `MoveRecordPage*.test.tsx`, `ServiceRequestDetailPage*.test.tsx` green.
**Reds read, not caused:** the ConfirmDialog census (`DEF-WRK-9721`, red since 368d908d7, 2026-10-04); en.json's American-English test on four FLOW cancel refusals (`DEF-CUS-9723`, red since 645a53660 — this lane's own four `canceled` keys were fixed before push).
**`OQ-CUS-12790`:** ruled (a) on 2026-10-05 (95705dfb8). Nothing on this screen is hard-coded to it: Cancel is held only while `cancel-preview` answers `allowed: false`, and a non-zero refund the preview serves is listed. When the server lane lands, the hold lifts with no screen change. **Landed 2.541.0 (lane RULINGS): the preview now answers `allowed: true` with the $175.00 refund for a held deposit.**
**Rollback:** redeploy 2.533.0 — no migration, the two keys are reads.

## 14 · Lane MVI-LIST-UI record (R2a, 2026-10-05) — version **2.536.0**

**P2.01 · P2.02 · P2.03 done** — the Move-ins list rebuilt from images 01 and 02 against §9.LIST.

| What | Where |
|---|---|
| Head on the Move-ins tab: kicker ACCOUNTS, title **Move-ins**, no sub-line, primary **+ New move-in** | `AccountsListPage.tsx` (header only) |
| Five tiles (To approve · Not started · Drafts · Starting this week · Waiting on a read), the server's whole-list counts; a tile not sent draws `—` | `MoveInsTab.tsx` `moveInsKpis` |
| Columns Reference · Customer · Unit · Services · Move-in date · Step · Opening read · Deposit · State, then one icon | `moveInsTableConfig` |
| `+ Filter ▾`: **Status** (To approve · Open · Completed → `f.status` groups) and **Service** (tenant's services, several → `f.service`); `f.state` is no longer sent | `moveInFilterGroups`, `MOVE_IN_LIST_FILTERS` |
| One icon per row from `action` — Review / Start / Resume / View — named and titled with the reference | `MoveInRowAction`, `moveInActionPath`; new kit glyph `ReviewIcon` |
| Footnotes S3/S4, the sort sentence and the list-level absences removed | `MoveInsTab.tsx` |
| Tests rewritten (24 cases), three guards broken by hand and seen red | `MoveInsTab.test.tsx`; `parkedDrafts.dom.test.tsx`, `screenVoice.guard.test.tsx`, `AccountsPage.test.tsx`, `AccountsCreateEntry.test.tsx`, `MoveEntryPoints.dom.test.tsx` amended |
| 46 new catalogue keys and 8 retired, all eleven catalogues | `10-scripts/i18n_fanin.py` |
| Walk at 1440, 13 checks | `10-scripts/cr171_movein_list_walk.mjs` (world: `10-scripts/cr171_movein_list_world.py`); photos `08-qa/movein-2026-10-05/after-list/A01-list.png`, `A02-list-filter-open-chips.png` |

**Judgments** (decision log 2026-10-05 *"MOVE-IN REDESIGN P2.01–P2.03"*): `DataTable` not `TableArray` for a paged register; the toolbar is B14 rule 12's (All chip = Clear all, ticks not radios, `▦` kept); the reference opens the details view on every row, the draft's Resume icon keeps `DEF-CUS-7900`; Discard moved off the row to the draft's details view; the kit's ghost icon, not the drawn bordered square.

**Left for others:** the server still serves `f.state` and the seven-step tiles (`kpis` legacy keys) because six backend suites assert them — retiring them belongs with LIST and those suites. **Reds read and not caused here:** `DEF-WRK-9721` (ConfirmDialog census, PartsPage — filed by MVI-DETAIL first; this lane's duplicate row was dropped before push), `DEF-CUS-9725` (ReturnedPostBanner refusal silent), `DEF-RAT-9348` (rail census, already filed).

**Rollback:** redeploy `2.535.0`. No migration, no stored fact changes.


### 13.1 · Screenshots at 1440 (builds 2.536.0, and 2.537.1 for 27–29 and x-enter-opening-read; each opened and checked non-blank), beside images 03–29

Folder `08-qa/movein-2026-10-05/after/detail/`, each named for its image:
`03-to-approve` · `04-to-approve-more` · `05-waiting-on-customer` · `06-waiting-on-customer-more` ·
`07-declined` · `08-declined-more` · `09-not-started` · `10-not-started-more` · `11-draft` ·
`12-draft-more` · `13-waiting-on-a-read` · `14-waiting-on-a-read-more` · `15-completed` ·
`16-completed-more` · `17-cancelled` · `18-approve` · `19-decline` · `20-ask-for-more` ·
`21-request-documents` · `22-request-messages` · `23-request-audit` · `24-unit-and-reads` ·
`25-account` · `26-billing` · `27-work` · `28-messages` · `29-audit`, and the undrawn doors
`x-reopen` · `x-change-date` · `x-enter-opening-read` · `x-cancel-committed` ·
`x-cancel-not-started` · `x-discard-draft` · `x-add-work-order` · `x-send-message`.
Data: `10-scripts/cr171_detail_seed.py` on the lane database (every status), photographed by
`10-scripts/cr171_move_in_detail_walkthrough.mjs`. *Add a work order* and *Enter opening read*
were each pressed through the screen (WO-0041 raised; MVI-26-0004 went Waiting on a read →
Completed).

**Found walking it, filed:** `DEF-CUS-9726` — a committed move-in can read *Waiting on a read*
while its own reads table says every register is read (the status wants a read on/after the
move-in date; the table caps as of it). Server fix for a P1 lane; the screen offers every meter
in *Enter opening read* meanwhile (2.537.1). **FIXED 2.545.1 (lane MVI-FOLLOW):** one definition —
a meter's opening read is its FIRST committed read dated on/after the move-in date
(`metering.selectors.reads_for_unit(since=)`, read by `move_record_reads._opening_reads` for a
move-in; the chip's `unit_reads_cell` already asked the same); the screen's every-meter fallback is
removed. A read the wizard dates BEFORE the move-in is not counted: `DEF-CUS-9741`, open. **`DEF-CUS-9722` FIXED 2.546.0 (lane MVI-FOLLOW):** image 29's *All · Changes ·
Messages* is drawn, each a server filter — `GET /audit-log?f.entity_id=<account>&f.kind=` (messages
= the account's `outbound_message` rows by `after.account_id`). **2.546.1:** the dead `customers.moveIn.cancel.depositHeld` refusal is retired (the server
cannot send it since 2.541.0); the DOM test now proves Cancel draws the PREVIEW's own refusal
(`billIssued`) rather than a held deposit. **`DEF-CUS-9728` FIXED 2.546.4:** the Unit & reads tab's Size prints
`size_name` (served since 2.538.0), as step 1 does; no size reads *—*. **Walked at 1440 on the lane database (lane DETAIL's seed), photographs
`08-qa/movein-2026-10-05/after/follow/` (6):** MVI-26-0004 reads *Waiting on a read*, tile *1 of 3*,
*Still open* E-5041 (its 3,817 kWh head predates the 10/03/2026 move-in, so it is the *Last read* and
not the opening); *Enter opening read* offers E-5041 and SM-7041 only; Size *Water 5/8"* /
*Electric 1φ 100A*; Audit *All* 7 rows · *Changes* 2 · *Messages* 5. `DEF-AUD-9727` — four move-in audit actions read
*"Activity recorded"*; described in 2.537.1.

## 15 · Lane MVI-WIZ-UNIT record (R2b, 2026-10-05)

### 9.UNIT · Step 1's server additions — `2.538.0`

| Door | Change |
|---|---|
| `GET /connections/proposed-work-orders?services=…&flow=move_in` | **new `flow`** (`move_in` · `move_out` · `transfer`): that flow's offer — the sequence-0 templates, rows as before (`template_id`, `template_no`, `name`, `job_type {id, name}`, `est_duration_minutes`, …), no rule preselection. Without `flow` the read is unchanged (New Connect step 6). |
| Complete's `field_visit.orders[]` (and every flow's) | **new keys** `template_id` (must be in the flow's offer, of the row's `type_id` → else 422 `work.fromFlows.templateNotOffered`) · `asset_no` (a meter on the flow's unit, any stage → else 422 `work.fromFlows.assetNotOnUnit`; the job stands on it) · `window_start` / `window_end` (ISO moments; written by the dispatcher's assign/schedule act; a refused window → warning `work_order_not_scheduled`, `work.fromFlows.notScheduled`, the order still raised). ⚠ At Complete a refusal inside the raise is the flow's `work_orders_not_raised` warning (`BR-WRK-055`), never a refused move-in. |
| `GET /units/{id}/move-in-meters` ROW | **new `facts`** `{serial_no, meter_type_name, read_method_name, installed_on, manufacturer, model, seal_no, certified_to}` — each `null` when not recorded (image 31). |
| Work › Accept on a `move_in` order standing on an asset at `inventory` | the asset → `active` (*Installed*), `install_date` = the order's completion day, `asset.installed` audit (`DEF-AST-9712`). |

### 15.1 · Step 1 · Unit on screen (P2.18–P2.21) — `2.542.0`

| Image 30 box | Built as | Reads |
|---|---|---|
| **Unit** — *Vacant unit\** + *Occupied units aren't listed.*, the unit card (number · label, address · building, *Vacant* · type · *First occupant*), **Building · Unit · Owner · History** | `MoveInUnitPick` (the wizard's) with the card as children; `StepUnit.UnitCard` | `GET /units/{id}/move-in-facts` |
| **Move-in date** — *Move-in date\**, *Rates and reads use this date.* | `DatePickerField` in its own `Panel` | — |
| **Services and meters** — fact *2 services · 2 meters · 1 device*; Start · Service · Meter · Size · Reads as · Last read · Opening read\* · ▸; footer *2 of 2 services start · 2 opening reads needed* | kit `TableArray` (read-only) with `rowNested` / `rowDetail`; `AffixField` with its unit | `GET /units/{id}/move-in-meters`, `POST …/check` |
| **Field visit** — *Visit needed*; # · Work order\* · For · Priority · Due · Window · Assign to · Note; *+ Add work order*; *Raised when you complete* | `FieldVisitOrders layout="panel"` (kit `TableArray`, `numbered`) | `GET /connections/proposed-work-orders?flow=move_in`, `/work/raise-options`, `/work/crews`, `/work/candidates` |

**Screenshots (1440, each opened and checked non-blank), beside images 30–32:** `08-qa/movein-2026-10-05/after/wizard/W30-unit.png`, `W31-unit-meter-details.png`, `W32-unit-read-below-last.png` — by `10-scripts/cr171_wiz_unit_walkthrough.mjs`.

**Differences from the images, recorded rather than built:** *Sized by W-5000 less W-5000-S1* / *Follows water* on an unmetered service (a rating fact the read does not serve — the row says *Not metered*); the drawn `8:00–12:00` is the product's *08:00–12:00* window (rule 37); the image's red underlined *+ Add work order* is the kit's secondary button (rule 44); buttons and spacing are our UI standard's.

**Hand-offs:** `DEF-CUS-9728` (DETAIL's Unit & reads tab prints the size code; `size_name` is now served) · `DEF-CUS-9734` fixed here (the Move-in completed sentence).

## 16 · Lane MVI-WIZ-CUST record (R2b, 2026-10-05) — versions **2.540.0** (server) and **2.543.0** (screen)

### 9.CUST · The Customer step's doors (P2.24, P2.25)

| Door | Body | Answer | Refusals |
|---|---|---|---|
| `GET /move-ins/documents/required` · `AdminOrClerk` | — | `{required: [doc_type, …]}` — the move-in checklist ticked on Settings, designed order; `[]` as shipped (BR-CUS-095) | — |
| `POST /move-ins/documents` · `AdminOrClerk` · multipart | `file`, `doc_type` (one of the request's nine), `name?` | 201 `{card_id, doc_type, name, size_bytes, content_type}` — stored NOW as an account document whose filing card id is `card_id`; filed nowhere yet | 415 / 413 (BR-SHL-031, `account_documents.checked_file`); `customers.serviceRequest.documentTypeUnknown` |
| `GET /move-ins/documents/{card_id}/content?as=view\|download` | — | the file, the account content view's headers | 404 once filed, or another utility's |
| Complete (`POST /units/{id}/move-in`, `POST /accounts/{id}/move-in`) — new key | `documents: [{card_id, doc_type}]` | `people.documents_carried` counts them with the request's | `customers.moveIn.documents.notStaged` (never staged, another utility's, already filed, a request's stored file) · `.documents.twice` — both before any write |
| `POST /accounts/{id}/co-owners/{coOwnerId}/photo-id` · `AdminOrClerk` · multipart | `file`, `name?` | 201 `{co_owner_id, photo_id: true, document_id}` — filed on the account (KYC) through `file_document`; the row points at it | 404 for a co-owner not on this account (HR-1); 415 / 413 |
| `GET /moves/{ref}` → `co_owners[]` | — | each row gains `id` (a handle, never shown) | — |

### What differs from images 33–40, and why (decision log *"MOVE-IN REDESIGN P2.22–P2.27"*)

* *Possible match* is drawn for New Connection's Q5 possible (name + date of birth), per the amended §9.IDN; image 35's *"Only the name matches."* is not built.
* The Documents table's **Note** column and the sentence *"Required ones come from Settings › Configure"* are not built (no home; rationale).
* The co-owner card's **Photo ID** is a disabled *Upload* with its reason; the upload lives on the Account tab after Complete.
* Government ID is the four-digit field; the mailing card has no Country (the kit's US address); the cards use the kit's *Expand ▾*.

### Tests

`06-backend/tests/test_cr171_p225_move_in_documents.py` (17: 16 on any database + 1 PostgreSQL; 17/17 on PostgreSQL 16) ·
`07-frontend/src/features/customers/moveInWizard/StepCustomer.dom.test.tsx` (20) · re-pointed: `MoveInWizard.test.tsx` TC-1,
`MoveInWizardDocuments.dom.test.tsx` §4 (the request's files now OPEN — the open half of `DEF-CUS-6002`; its list half is not
this lane's), `moveInFromRequestPrefill.dom.test.tsx` (a company also fills Business type and the contact person).
## Lane MVI-WIZ-REV record (R2b, 2026-10-05) — version **2.544.0**

**Built (P2.32 · P2.33 · P2.34, and this lane's share of P2.35 · P2.36 · P2.39):**

| What | Where |
|---|---|
| Step 4 · Review — **Unit** (Unit · Address · Previous · Services · Move-in date · Opening read · Field visit), **Customer** (Customer ID · Legal name/Full name · Trading as · Customer type · Business type · EIN/SSN · State of formation · Contact · Owners/Co-owners · Email · Phone · Bills go to · PO on bills · Documents · Mailing address; company rows only for a company), **Billing** (Plan · Preferences · Discounts · Tax · Fees · Payment · Account number), each with **✎ Edit** to its step | `moveInWizard/StepReview.tsx` |
| The kit's `FactBlock` gains `variant="rows"` — label left on a tinted sixth, value right, one ruled row per fact (image 45) | `components/FactBlock.tsx` |
| **Messaging** — `TableArray`: SEND · MESSAGE * · TO · CHANNEL · WHEN; the server's defaults as facts; **+ Add message** rows → Complete's `extra_messages`; *n will send* | `MoveInMessages.tsx`; state in `useStepReviewOwn()` (payload, park, hydrate) |
| **Edit** (`?request=<id>&edit=1`, §9.DETAIL) | `moveInWizard/useMoveInEdit.ts`; minimal `MoveInWizard.tsx` hunks (below) |
| 86 catalogue keys in all eleven (written in each language), 4 overwritten to the drawing's words, 4 retired (`review.title`, `messages.colSays`, `.colTemplate`, `.onCommit`) | `10-scripts/i18n_fanin.py` |
| `useMoveInEdit.ts` on the Route B ledger | `styles/route-b-migrated.txt` |

### 9.REV · the one read this lane added — `2.544.0`

| Door | Answer |
|---|---|
| `GET /move-ins/message-templates?search=` (`AnyTenantRole`, `move_in_flow_api.move_in_message_templates`) | `{served, results: [{code, name}]}` — `notifications_seam.message_templates()` (the call Complete queues wording through) minus `move_in_welcome` and `service_agreement`; `search` narrows by the name. `served: false` = notifications published nothing. |

**What Edit does, by status** (PO ruling J3, *"on edit of Move in request use same form Add form to edit"*):

| Status | Opens | Writes | Title | Last step |
|---|---|---|---|---|
| To approve · Waiting on customer (`editable`) | `GET /service-requests/{id}/move-in-form` values | `PUT …/move-in-form` on *Save draft & exit* and on the last step; **no autosave, Park held** — so no second draft | *Edit move-in · SR-…* | **Save changes ✓**, back to `/moves/SR-…` |
| Not started (approved; PUT refuses) | the same values; `?parked=<park_id>` so the autosave PATCHes the request's park | the park (autosave) | *Edit move-in · MVI-…* (from `GET /moves/SR-…`'s `reference`) | Complete move-in ✓, as *Start* |
| Draft | `resumePath` (unchanged, P2.17) | the draft | *Edit move-in · MVI-…* | Complete move-in ✓ |

**`MoveInWizard.tsx` hunks (lane WIZ's file, kept to what the Edit door needs, re-derived from the tip at push):** the park `onHydrate` body became `applyValues(values)` so a draft and an edit fill the form through ONE function; the park's `values` object is hoisted to `parkValues` (the PUT sends the same object); `autosave` is off while an edit is read and on an undecided request; Park is held on a request; the title takes the edit's reference; *Save draft & exit* and the commit go through `saveRequestEdit()` in request mode; `MoveInShell` takes a `commitLabel`.

### What differs from images 45–47, and why

| Image | Drawn | Built | Why |
|---|---|---|---|
| 45, 46 | Defaults' TO / CHANNEL / WHEN as dropdowns, SEND live | text, SEND disabled and ticked from the server's channels, ✕ held *Sent by default.* | Complete has no parameter for a default (`defaultTwice`); a live control over a door that ignores it is law 2's mirror |
| 45 | *Registered in* | **State of formation** | `register` is meter-sense only in `customers.*` (DEF-CUS-6422's guard) |
| 45 | *Mailing address · As entered* | *Same as service address*, or the address | *As entered* says neither which nor what |
| 45 | Customer rows of a company | a person draws Full name · SSN · Co-owners and no company rows | the same section for both kinds |
| 45 | *Opening read · W-5000 · 1,000 kgal* | the meter, the value as typed, and the meter's unit from `move-in-meters` | hard rule 3; a value with no known unit shows the meter only |
| 45 | *Field visit · Move-in read · 15 min · R. Patel · 2026-10-10 8:00–12:00* | job type · assignee · due date | the row's template, minutes and window are WIZ-UNIT's (P2.21) and not yet in `FieldVisitRow` |
| 47 | Park on an edit | held on a request (*A request is saved, not parked.*) | a Park would mint a second move-in |

**Proved (red first, each quoted in its file):** `moveInWizard/useMoveInEdit.dom.test.tsx` 4 cases — all 4 red against the tip's `MoveInWizard.tsx` (*expected '' to be 'unit-b'*, *toBeDisabled*, *Unable to find … Edit move-in · MVI-26-0011*), green after; `moveInWizard/StepReview.dom.test.tsx` 8 cases — 8 red against the tip's step, then three guards broken by hand (company block, SSN whole, ✎ Edit target) each red; `MoveInMessages.dom.test.tsx` 16 cases — defaults' box live, unticked row sent: 3 red; `FactBlock.dom.test.tsx` +1 (grid-cols-4 → red); `MoveInWizard.test.tsx` 3 review cases re-pointed (47 passed); backend `tests/test_cr171_p233_move_in_message_templates.py` 3 cases (red: `Resolver404`, `AttributeError … template_choices`), 3 passed.
**Reds read, not caused:** `usEnglishCatalogue.test.ts` (five `cancelled` values — `DEF-CUS-9723`, red since 645a53660).
**Rollback:** redeploy `2.543.2` (the build before 2.544.0). No migration.

### After-walk at 1440 — `2.543.1` (photographs beside images 33–40)

`10-scripts/cr171_wiz_cust_seed.py` puts a person with an SSN (Nilesh G) and a company with a Tax ID (Kestrel Holdings
LLC) on a lane database; `10-scripts/cr171_wiz_cust_walkthrough.mjs` walks step 2 on 8 Quarry Lane · SCW-U-303 and
asserts each state is on screen before it photographs it. **10/10 checks** into
`08-qa/movein-2026-10-05/after/wizard-customer/`:

| Photo | Beside image | State |
|---|---|---|
| `33-customer-person.png` | 33 | person, co-owner card closed (its summary line), documents, mailing = service address |
| `38-co-owner-open.png` | 38 | the co-owner card open |
| `35-search-possible-name-and-dob.png` | 35 (re-cut) | an SSN nobody holds but Nilesh G's name AND date of birth → *Possible match* (Q5) |
| `35b-name-only-not-shown.png` | 35 (superseded) | a name alone → *New customer*; no match block is drawn |
| `36-search-new.png` | 36 | *New customer — No customer found. New ID given on complete.* |
| `34-search-found.png` | 34 | the SSN on file → *Existing customer* with the accounts table |
| `37-search-linked.png` | 37 | *Linked* with *Unlink* |
| `39-document-added-mailing-entered.png` | 39 | a *Tenancy agreement or deed* row uploaded (staged), mailing typed |
| `40-customer-company.png` | 40 | company: legal name … registered in, Tax ID linked, contact person filled from the link, an officer card |

Then **Continue reaches step 3** from the complete company step. Found by the walk and fixed here: the second dropdown read
*Sub-category* (New account's word); image 33 says *Sub-type*. **Not walked to Complete in a browser:** step 1 on a metered
unit needs its opening reads and step 3 is still the pre-redesign body (WIZ-BILL's), so a full browser Complete is P4's;
the commit body this step adds is proved by `StepCustomer.dom.test.tsx` and the server's acceptance of every key by
`test_cr171_p225_move_in_documents.py` and IDN's `test_cr171_p110_move_in_people.py`.

### After-walk at 1440 (build 2.545.0 → fixed in **2.545.3**)

`10-scripts/cr171_move_in_review_walkthrough.mjs` on the lane database (`seed_demo`, `load_sample_data`, `cr171_detail_seed.py`), photographs in `08-qa/movein-2026-10-05/after/review/`, each opened and checked non-blank:

| Photograph | Beside image | What it shows |
|---|---|---|
| `W45-review.png` | 45 | Review: Unit · Customer · Billing (✎ Edit each), Messaging with the two defaults, *1 will send* |
| `W46-review-message-added.png` | 46 | *+ Add message*: a published message picked, the customer, Text message, On complete; *2 will send* |
| `W45b-edit-to-customer.png` | — | ✎ Edit on Customer opens step 2 |
| `W47-edit-request.png` | 47 | Edit on To approve SR-26-0009: *Edit move-in · SR-26-0009*, Park held (*A request is saved, not parked.*) |
| `W47b-request-saved-back.png` | — | *Save draft & exit* wrote back and returned to SR-26-0009's details view; the database holds ONE park for it, reference SR-26-0009 |
| `W47c-edit-not-started.png` | 47 | Edit on Not started: *Edit move-in · MVI-26-0001* |

**Found walking it, filed first, fixed (red first, quoted in the test files):** `DEF-CUS-9735` — Edit/Start on a Not started move-in minted a NEW `MVI-` draft on every open (read back: MVI-26-0009, MVI-26-0011 for one job); now one draft referenced MVI-26-0001, resumed on the second open (`useMoveInEdit.dom.test.tsx` +2: *Unable to find … MVI-26-0011* / *expected '' to be 'unit-b'* → green). `DEF-CUS-9742` — Review's Tax read *Not exempt* with the Billing step's Tax tick on (`expected 'Not exempt' to be 'Exempt'` → green). Judgment: a request with no service rows no longer unticks every service (decision log).
**Reds read, not caused:** `retiredWords.test.ts` names `customers.moveIn.customer.registeredIn` (*Registered in*), lane WIZ-CUST's key from `0e9b22d99` — the same guard this lane met and answered with *State of formation*.

## 16 · Lane MVI-WIZ-BILL record (R2b, 2026-10-05) — version **2.545.0**

**Built (P2.28–P2.31, P2.35/P2.36/P2.39 shares):** step 3 is six panels in the drawn order —
**Plan** (with *See full rates*), **Preferences**, **Discounts**, **Tax**, **Fees**, **Payment** —
replacing the old body (unit pricing panel, two bare ticks, tax fields, the hand-typed discount
list and the whole Deposit form). Files: `moveInWizard/StepBilling.tsx` (composes; own state =
`ctx.own.billing`), `billingModel.ts` (state, payload, park/hydrate, what holds Continue),
`MoveInPlanPanel.tsx`, `BillingExtras.tsx`, `FeesTable.tsx`, `MoveInPayment.tsx`,
`api/moveInMoneyEndpoints.ts`. ONE read (`GET /move-ins/pricing`) serves the Plan panel,
*See full rates* and the Fees table's plan rows, so the table and the plan cannot disagree.

**What the step adds to Complete (§9.MONEY, merged last):** `fees` (plan rows + added codes),
`deposit: {decision: "required", amount}` when the plan asks one (the money is `payment`'s),
`payment` (`add_to_bill` alone, or `pay_now` with method, amount, check number, received),
`discount_claims`, `tax_exemption` with the certificate as base64, and `tax_exempt` /
`tax_exempt_ref` / `tax_exempt_expires`. Paperless, text reminders, autopay and portal language
stay the wizard's `preferences`, written by this step's dropdowns. **Worked (J4), asserted:**
DEPOSIT $150.00 + CONNECT $25.00 + RUSH $40.00 = **$215.00**; Pay now $100.00 by check →
*"$115.00 goes on the first bill."*; Add to bill → *"$215.00 goes on the first bill."*

**What differs from images 41–44, and why (each recorded, none silent):**
* no **Taxable** column on Fees (drawn *Yes* beside CONNECT) — `OQ-BIL-12788` (a): a move-in fee
  is never taxed at move-in; a ruling beats a drawing;
* *See full rates* keeps `PlanSections`' own section order and columns (services, charges, taxes,
  deposits, discounts); *Rate filing* / *Plan for* are not drawn (not served); the meters table
  shows ID · Kind · Size — the drawn *Name* is not served, and the size is the stored size code
  (the same gap as `DEF-CUS-9728` on the details view);
* Discounts shows Discount · Amount · Note — the drawn *Type* and *On* are not served on a plan's
  discount row;
* *Autopay from* is drawn and held, with *"No saved payment method."* — no read lists a
  customer's saved methods (`DEF-CUS-9739`), and a new customer has none;
* ~~the plan's deposit row cannot be waived on this step (the drawing has no waive) — the old Deposit
  step's waive is gone with it (decision log, judgment (6));~~ **SUPERSEDED 2026-10-05 by PO ruling
  (7)** (decision log *"A CLERK CAN STILL WAIVE THE DEPOSIT"*): the deposit row carries a **Waive
  deposit** row action with a required reason — built 2.548.0, lane RULINGS-2, §16;
* nothing anywhere draws *held for a System Admin* — ruling (2) of 2026-10-05, built server-side by
  lane RULINGS in 2.539.0.

**Defects:** `DEF-RAT-9738` filed and fixed (the Base charge was the whole plan's, $20.00 for a
water-only move-in that bills $8.00) — red first on `test_cr171_wiz_bill_base_total.py`
(`assert … == {'amount_display': '8.00'…}` failed with 20.00), 31 passed after;
`test_cr171_p1_16_move_in_pricing.py`'s fake sections given the `state`/`flat_display` keys the real
read always serves. `DEF-CUS-9739` filed (open; screen mitigation in place). `DEF-RAT-9740` filed and fixed — found on
the walk: *See full rates* went to the application error page (`Cannot read properties of null
(reading 'id')`) on a plan whose deposit is a TYPED rule, which `plan_reads._deposits` serves with
`ref: null` by design, and the plan pages' normaliser silently DROPPED that $150.00 row; the
sections read now keeps it (`PlanSectionDeposit`, ref nullable for that read only) and draws it as
*Deposit*; red first in `PlanSections.dom.test.tsx`. `DEF-CUS-9729` (lane WIZ's seam) consumed —
the step reads `ctx.own.billing`.
**Tests:** `moveInWizard/StepBilling.dom.test.tsx` 12 cases (mutation-proved: `onFirstBill`
returning the total turns two red, `expected '215.0000' to be '115.0000'`); `MoveInWizard.test.tsx`
re-pointed — the two seven-step billing cases become one four-step case, and the nine
pricing-panel cases mount `UnitPricingPanel` directly (the unit's Plan tab still uses it).
**Walk world:** `10-scripts/cr171_wiz_bill_world.py` (Residential Standard asks $150.00, names
CONNECT $25.00; RUSH $40.00 is a one-time code).

**Walked at 1440 on the lane database** (`10-scripts/cr171_wiz_bill_world.py`, then
`10-scripts/cr171_wiz_bill_walkthrough.mjs`, unit U-00318-101, build **2.545.0** as pushed), each
PNG opened and checked non-blank, beside images 41–44 — folder `08-qa/movein-2026-10-05/after/billing/`:
`B41-billing.png` (every tick on, *Fees total $175.00*, *All fees paid now…*) ·
`B42-full-rates.png` (the narrowed plan, meters and devices per service, the typed $150.00
deposit) · `B43-fee-added-part-payment.png` (RUSH $40.00 → **$215.00**, $100.00 by check →
**"$115.00 goes on the first bill."**) · `B44-add-to-bill-sections-unticked.png` (**"$215.00 goes
on the first bill."**) · `B45-review-after-billing.png` · `B48-completed-j4.png` (*Fees $215.00
posted · DEPOSIT, CONNECT, RUSH* · *Payment $100.00 received*). **Read back from the database**
for that account (AC-2026-00057, MVI-26-0010): three `move_fee_lines` 150.0000 / 25.0000 / 40.0000, one payment 100.000000
`prepay` with confirmation 1043, and AUTOPAY and PAPERLESS enrolled at once (`not_required`) —
no System Admin step.
**Also different from the drawing, by the kit:** a plan row's ✕ is drawn disabled with *Plan rows
stay* as its reason (BR-SHL-025) where image 41 draws none; *See full rates* is the kit's
`Disclosure` (*Expand ▾*), and the certificate is the kit's file field.

## 16 · Lane RULINGS-2 record (2026-10-05) — the PO's rulings (A), (B), (C), (5) and (7)

Decision log rows *"FIVE PO RULINGS IN ONE REPLY"* and *"A CLERK CAN STILL WAIVE THE DEPOSIT"*.

**(A) `DEF-CUS-9724` — 2.546.5.** PO, verbatim: *"(a) An exemption removes only the tax named on its
certificate. The church pays $6.25."* Where the flag was set: lane MVI-MONEY's
`move_in_preferences._account_values` (2.529.0) merged `tax_exempt: True` (+ reference and expiry)
into the account write whenever a `tax_exemption` block arrived, and lane RULINGS (2.539.0) kept it;
lane WIZ-BILL's `billingModel.billingPayload` (2.545.0) ALSO sent `tax_exempt: own.taxOn`,
`tax_exempt_ref` and `tax_exempt_expires` beside the block. Both are gone: the step sends
`tax_exempt: false` and only the block; the server (`merge_account_values`) drops the three blanket
columns from the write whenever a block is present. **Red first** (PostgreSQL-ready test
`tests/test_def_cus_9724_exemption_removes_only_its_own_tax.py`, priced as a bill run prices it —
the blanket flag through `gather._tax_exempt_on`, the certificate through `plan_tax_rules`):
`AssertionError: assert Decimal('0.00') == Decimal('6.25')`; green on SQLite and on PostgreSQL 16
(7 passed with `test_cr171_p1_29_money_pg.py`). The front-end case went red
(`expected true to be false`) on the old payload and green on the new. Nothing stored is rewritten.

**(C) `DEF-GOV-9733` — no version (no product code).** PO, verbatim: *"(a) Add them to the list, as you
did for the three fee files."* `payments/deposit_release.py` and `payments/deposit_release_models.py`
are on `10-scripts/gates/human_owned.txt`, each line saying what the PO was shown (Nilesh's $150.00
released, one $175.00 refund). G53 before: FAIL naming 4 files; after: FAIL naming 2, neither this
ruling's (`customers/co_owner_models.py`, `work/raise_svc.py`). G07 PASS (865 guarded files conform).

**(B) The human sign-off for the deposit release — recorded, no version.** PO, verbatim: *"Nilesh's
credit becomes $25.00 + $150.00 = $175.00, and one $175.00 refund goes to Finance for approval. - (a)
Approve all four."* A new review-ledger AMENDMENT row for `payments/0047`, `0048`, `deposit_release.py` and
`deposit_release_models.py` reads **RATIFIED 2026-10-05** (the original row is left as written) on exactly the four statements shown,
quoting the decision-log row; their docstrings keep `HUMAN-REVIEW-PENDING`, because G7 requires that
marker for the life of a guarded file and the ledger row carries the state (G7's own docstring). A
new test asserts all four statements (`test_the_four_statements_the_po_signed_on_2026_10_05`, proved
red by dating the entry the 1st). Not covered by the signature and still on the agenda: `0048`'s
tenant-isolation policy itself, and `move_in_cancel.py` with the two credit reads.

**(7) Deposit waive on the Billing step — 2.548.0.** PO, verbatim: *"(a). Clerks use it today, the
server already supports it, and the fix for \"waived deposit still billed\" is already in place."*
Built: the Fees table's deposit row carries a **Waive deposit** icon (`CommitIcon`, B14 rule 15)
that opens the kit's `FormModal` asking **Waive reason** (required — blank keeps the deposit
charged); a waived row stays drawn — *Waived* pill, the amount struck, the reason in Note — and an
**Undo waive** icon (`RollBackIcon`) puts it back. The kit gained one opt-in, `rowActions` on
`EditableTable` / `TableArray` (B14 rules 36, 43 — absent draws nothing, so no other table moves).
**What is sent is the server's existing waive**, the old Deposit step's shape
(`depositCapability.depositPayload`): `deposit: {decision: "waived", amount, waive_reason}`, and
the deposit row is LEFT OUT of `fees` (the server refuses one beside a waive,
`move_fees.DEPOSIT_NOT_OWED`); `move_fees.record` writes no deposit line and `first_bill`
skips it (`DEF-BIL-9709`, 2.529.0). **The figure:** $150.00 + $25.00 + $40.00 = $215.00; waived,
the Total reads **$65.00** and Add to bill reads *"$65.00 goes on the first bill."* Review shows
**Deposit — Waived · Hardship** under Fees. **No server change** — the role gate (Billing Clerk or
System Admin, `deposit.WAIVE_ROLES`) and the reason refusal are the server's, as on the old step.
**Tests:** `StepBilling.dom.test.tsx` 4 cases + `StepReview.dom.test.tsx` 1, all red first
(`expected '215.0000' to be '65.0000'`, *Unable to find … "Waive deposit"*) and green after;
`tests/test_cr171_rulings2_deposit_waive_billing_step.py` (Marcus, a Billing Clerk, sends the
step's exact body: lines CONN + RUSH only, $65.00 prepay, the waive and *Hardship* kept on the
account, `first_bill._deposit_waived` True) — green on SQLite and PostgreSQL 16. New keys
(`customers.moveIn.fees.waive|waiveSubmit|undoWaive`, `customers.moveIn.review.deposit|depositWaived`)
in all eleven catalogues through `i18n_fanin.py`, written in each language.
**Walked at 1440 on the lane database** (PostgreSQL 16, build **2.548.0** as pushed;
`10-scripts/cr171_wiz_bill_world.py`, then `10-scripts/cr171_rulings2_waive_walkthrough.mjs`, unit
U-00102), each PNG opened and checked non-blank — folder `08-qa/movein-2026-10-05/after/waive/`:
`W1-waive-reason.png` (the dialog, *Waive reason* required, Total still $215.00) ·
`W2-deposit-waived-billing.png` (DEPOSIT *Waived*, $150.00 struck, *Hardship* in Note, Total
**$65.00**, *"$65.00 goes on the first bill."*) · `W3-review-deposit-waived.png` (*Deposit — Waived ·
Hardship*, Fees *CONNECT $25.00 · RUSH $40.00 · total $65.00*) · `W4-completed.png` (*Fees $65.00
posted · CONNECT, RUSH*). **Read back:** AC-2026-00001 `deposit_waived_amount` 150.0000, reason
*Hardship*, `move_fee_lines` CONNECT 25.0000 and RUSH 40.0000 — no deposit line.

## 17 · Lane MVI-I18N record (R3, 2026-10-05) — version **2.547.0**

**P2.37 — the eleven catalogues for every move-in key round 2 added, in each language's own words
(B14 rules 33, 34, 35). NATIVE-REVIEW-OWED.** Read: all **708** keys round 2 added or changed
(`customers.moveIn.*`, `customers.moveDetail.*`, `customers.moveIns.*`, two `work.*` families),
in ten languages beside English, plus the **99** older keys of the same families.

**Defects, filed before the fix:** `DEF-CUS-9745` (the Customer step said *Registered in* — a
retired word, `retiredWords.test.ts` red — where Review says *State of formation*; both steps now
carry one word in all eleven), `DEF-CUS-9746` (G15: **91** values pasted in English), `DEF-CUS-9747`
(two or three words per concept per language, and wrong-meaning lines).

**What changed (212 keys, 577 values, plus 15 retired; full reasoning in the decision log row of this date):**
* **One word per concept per language**, taken from the module the clerk navigates to where one
  exists — unit = the Units nav word, work order = the Work orders title, French plan = *forfait*
  (*Forfaits et tarifs*); otherwise the word a utility clerk says — the move-in is it *subentro*,
  hi *मूव-इन*, id *pindah masuk*, pt *mudança*, es/es-MX *alta* (its date stays *fecha de
  mudanza*); account co-owner fr *cotitulaire*, es/pt *cotitular*, it *cointestatario*, ko
  *공동 명의자*; opening read ja *入居時検針*, ko *입주 검침*, fr *relevé d’entrée*, id *pembacaan awal*.
* **Wrong meanings corrected:** it toast *"è stato trasferito"* → *Subentro completato sul conto…*;
  id *lusa* (day after tomorrow) → *keesokan harinya*; fr *Emménagement complet ✓* → *Terminer
  l’emménagement ✓*; ja *引っ越し* → *入居*; ko toast *이전되었습니다* (transferred) → *입주가
  완료되었습니다*; it/ko/ja/fr/pt/id *unit.stillOccupied* rewritten from word-for-word MT.
* **The 91 English values:** plan versions take the Accounts page's own per-language form
  (de *V3*, es/fr/it/pt/id *v.3*, hi *सं3*, ja *第3版*, ko *제3판*); LLC as each language writes the US
  form (fr *SARL*, it *Srl*, ja *合同会社*, ko *유한책임회사*…); SSN as New Connection wrote it
  (de *SV-Nummer*, es *NSS*, fr *N° SS*…); EIN with the Customer step's gloss; *total* written
  (es *en total*, fr *total :*, id *jumlah*, pt *total de*); the meter ID column takes the plan
  table's *Número/Numero/Nomor*. Kept by the PO's native-speaker test: a no-space percent
  (`{{value}}%`, `{{pct}}%`) on hi/id/it/ja/ko/pt's G15 lists, and `{{unit}} · {{was}} → {{now}}`
  (no word in it) on G15's UNIVERSAL list.
* **Rule 34:** *{{total}} posted* is in the books — es/es-MX *contabilizados*, it *contabilizzati*,
  hi *बहीखाते में*, ko *장부 반영* (they read as *recorded*).
* **Spanish move-in copy in one register** (*tú*, as the newer screens were).
* **Retired** through `i18n_fanin.retire`: fifteen keys of the seven-step wizard nothing reads
  (`customers.moveIn.carryAbsent`, `.field.depositCarry`, `.field.unit`, `.plan.arrives`,
  `.plan.arrivesTitle`, `.plan.hint`, `.plan.refusedWhy`, `.plan.title`, `.preferences.hint`,
  `.preferences.title`, `.step.deposit`, `.step.plan`, `.step.preferences`, `.step.services`,
  `.step.start`) — grep of the whole repo outside the catalogues: zero readers.

**Proof.** `src/i18n/moveInOneWord.test.ts` (new): red first — **12 failed** on the tip (it-IT
*customers.moveIn.commit = Trasferimento completo ✓*, hi *प्रवेश पूरा करें ✓*, …; de's Customer
step word ≠ Review's), green after (22 passed). `retiredWords.test.ts` red on the tip
(*customers.moveIn.customer.registeredIn = Registered in*), green after. `src/i18n/` 7 files /
117 tests green. **G15**: *FAIL: 91 NEW value(s)* → *PASS … 2937 still identical (2937 baselined)*,
run through `run_gates`'s own registry entry. Move-in screen suites (`moveInWizard/`,
`moveDetail/`, `customerMatch/`, `MoveInWizard`, `MoveInsTab`, `AccountsPage`, `MoveRecordPage`,
`parkedDrafts`, …) green. `StepReview.dom.test.tsx`'s person case listed *Registered in* among the
labels a person must NOT see — a word no screen printed, so it could not fail; it names *State of
formation* now.
**Red I did not cause:** `MoveEntryPoints.dom.test.tsx` › *a FIRST OCCUPANT's deposit step reads
the plan's figure…* fails at `6bf3c9726` in a clean worktree before any change of mine (it drives
the seven-step wizard's Deposit step, which the four-step wizard no longer has).
**Not done here:** other flows' words (the move-out's hi *गृह-त्याग*, ja *占領されました* for
*Occupied* in `metering.units.occupancyFilter`) — outside the move-in families, reported.

## 17 · Lane MVI-E2E-SEED record (R4 preparation, 2026-10-05) — P4.01 and P4.02, no version

**Test tooling only, so no version** (§8.2's P0 precedent: no product code ships). Decision log
*"MOVE-IN END-TO-END P4.01 + P4.02 — THE MATRIX WORLD AND ITS RUNNER"* holds the six judgments.

### 17.1 · P4.01 — the world (`10-scripts/cr171_e2e_matrix_world.py`)

On a fresh, migrated lane database: `… cr171_e2e_matrix_world.py setup` (idempotent; ~4 min, most of
it `load_sample_data`), then `… world` prints the seeded cases as JSON. It signs up **Cedar Ford
Utilities** (`mvimatrix`, eight services) through `provision_tenant`, loads its sample set, adds the
clerk **Jo Ramirez** (Billing Clerk) beside the owner Marcus Lee (both `S3cure!passw0rd`), and builds:

| Case | Unit (address · label) | Plan | Service points | Equipment (one 09/30/2026 read per meter, in its own unit) |
|---|---|---|---|---|
| M1 | U-00004 · 41 Larkspur Lane · Unit 1 (single-family) | SCW-RES | electric, water, sewer, trash | E-M1 kWh 4,210 · W-M1 kgal 312.4 · cart TR-M1-1 |
| M2 | U-00005 · 300 Willow Court · Apt 2B (apartments) | SCW-RES | water, sewer | W-M2 kgal 118.0 · irrigation sub-meter SW-M2 41.0 under it · backflow BF-M2 under it |
| M3 | U-00006 · 18 Juniper Street · Unit 1 | SCW-RES | electric, gas | E-M3 kWh 8,820 · G-M3 ccf 1,530 |
| M4 | U-00007 · 900 Commerce Row · Suite 110 | SCW-COM | electric, water, sewer, trash, storm water | E-M4 · W-M4 · two carts |
| M5 | U-00008 · 12 Chapel Road · Sanctuary (inside city) | SCW-COM | water, sewer, fire | W-M5 · fire lines FL-6 + FL-2 + FL-2 (signup prices $60.00 + 2 × $12.00 = **$84.00**) |
| M6 | U-00009 · 5 Foundry Way · Bay 3 | SCW-IND | electric, gas, water, solar | E-M6 · G-M6 · W-M6 · PV-M6 SOL-P8 behind E-M6 |
| M7 | U-00010 · 77 School Lane · Main campus (government, inside city) | SCW-COM | water, sewer, trash | W-M7 · three carts |

Plus: deposit rules RES/residential $150.00, COM/commercial $300.00, IND/industrial $500.00 (none
for government); `CONN` $25.00 on every plan, `RUSH` $40.00 to add; `AUTOPAY` + `PAPERLESS` on every
plan, `CAP` on `SCW-RES`; *City of Cedar Ford utility tax* 2.00% (commercial, government) on every
plan through the City jurisdiction, with exemption categories `RELIGIOUS` and `GOVERNMENT`, each
asking a certificate; **Rosa Delgado** (SSN …7781, born 04/12/1979) with AC-2026-00054 owing $50.00
and AC-2026-00055 owing $34.20 = **$84.20** (cutover opening balances through
`ledger.opening_balances`); **Northgate Provisions LLC** (Tax ID …1190) with AC-2026-00056. Every
unit on cycle `CY-001` (Silver Creek — monthly) and route `RT-006` *Matrix walk*.
**Verified:** the seven units list as vacant on step 1; Search customer ID finds Rosa by SSN with both
accounts and Northgate by Tax ID — and reads Rosa's total as **$0.00**, filed `DEF-CUS-9756`.

### 17.2 · P4.02 — the runner (`cr171_e2e_matrix_run.mjs` + `cr171_e2e_matrix_readback.py`)

`DATABASE_URL=… MX_BASE=http://127.0.0.1:<port> MX_CASES=M1 MX_OUT=<folder> node 10-scripts/cr171_e2e_matrix_run.mjs`.
Per case: (1) the four steps through the browser at 1440 as the clerk; (2) the readback (writes
nothing; the first-bill preview runs in a rolled-back transaction); (3) the screens: unit, each meter
and its Reads tab, the account, its Payments tab, the move's Billing tab, the route, each work order,
the move's Messages tab and the move record; PASS/FAIL per check, a count per case, exit 1 on any FAIL.
**For the R4 lanes:** M2–M7 each need a `CASES[key]` entry in the runner (the clerk's input) and an
`EXPECT[key]` in the readback (what follows from it); a case without them reports one FAIL naming that.
Reset between runs by restoring a dump taken right after `setup` (a run commits a move-in).

### 17.3 · M1, run on build 2.545.3 — **107 PASS · 7 FAIL**, every FAIL a filed defect

MVI-26-0008, Avery Collins, AC-2026-00057; 17 photographs at 1440 and the run's own output in `08-qa/movein-2026-10-05/e2e/M1/`.
Passing, among the 107: the four services listed and both opening reads asked on step 1 · *Search
customer ID* answers *New customer* and draws no match · Fees total **$175.00** (DEPOSIT $150.00 +
CONN $25.00), no Taxable column · account active, Residential · Single-family, opened 10/10/2026, four
agreements from 10/10/2026 · E-M1 4,300 **kWh** and W-M1 315 **kgal** committed on 10/10/2026 · the
unit stores no status and holds one open account (reads *Occupied*) · no asset status written · two
check payments of $150.00 (deposit) + $25.00 = $175.00, check 2041, each audited; 0 journal entries
read because both are still processing (printed, not hidden) · no tax on any fee · cycle and route
on every service point · WO-0053 from the move-in, *Opening read* (type *Re-read*) for W-M1,
10/10/2026 08:00–12:00, assigned, no labour · welcome queued on email and letter, receipts queued,
nothing *sent* · every screen opens.

| FAIL | Defect |
|---|---|
| Move-in completed prints `deposit_payment_has_not_cleared` | `DEF-CUS-9749` |
| Move-in completed reads *Messages 0 queued* (welcome email + letter were queued) | `DEF-CUS-9757` |
| First-bill preview cannot price: sewer's `no_meter` treated as a missing read | `DEF-BIL-9750` |
| First-bill preview bills the $150.00 deposit again while the check is processing | `DEF-BIL-9751` (money — for the PO) |
| Move's Billing tab dates the payment 10/09/2026 (typed 10/10/2026) | `DEF-CUS-9754` |
| Move's Billing tab: *Still to collect $150.00* right after the deposit was taken | `DEF-CUS-9755` |
| Move record stays *Waiting on a read*: the trash cart counts as an unread meter | `DEF-CUS-9753` |

Also filed from the walk: `DEF-CUS-9752` (step 1 labels Trash *Metered*). **No product file was
changed by this lane.**

## 17 · Lane MVI-PROOF record (R3, 2026-10-05) — P3.01–P3.06 and P3.08; version **2.548.1**

Worked on its own PostgreSQL 16 database (`sbh_wmproof`: `seed_demo`, `load_sample_data`, then every
`10-scripts/cr171_*` seed and world), backend 8742, front end 5742 (`vite build --mode compose`).

### P3.01 · Guards broken first, through the harness that runs them (law 7)

Most lanes quoted their own reds (§10–§16). These had no recorded red and were broken here, each in
pytest — the harness that runs them — then restored and seen green:

| Guard | Broken how | The red, verbatim | Harness |
|---|---|---|---|
| `move_in_cancel` — the SAVEPOINT round Work's cancel (law 14) | `with transaction.atomic():` → `if True:` | `django.db.utils.InternalError: current transaction is aborted, commands ignored until end of transaction block` | pytest, `config.settings.pgtest` (PostgreSQL 16) |
| `move_in_complete.pop` — a default named as an extra (`defaultTwice`) | the check made `if False and …` | `Failed: DID NOT RAISE ValidationError` (`test_a_default_named_as_an_extra_is_refused_and_nothing_is_written`) | pytest, SQLite |
| `move_in_documents` — the same card twice (`documents.twice`) | `if card in seen` → `if False and …` | `django.db.utils.IntegrityError: UNIQUE constraint failed: account_documents.tenant_id, account_documents.document_id` (`test_the_same_card_twice_is_refused`) | pytest, SQLite |
| `move_fees._price_check` — a fee figure that is not the code's | the comparison made `if False and …` | `Failed: DID NOT RAISE ValidationError` (`test_p1_12__a_figure_that_is_not_the_codes_refuses_the_whole_move_in`) | pytest, SQLite |
| The nineteen (`MOVE_IN_NINETEEN_BREAK`) | `--prove-red` | M1 `payment_rows`: 1 failed; R1 `refusal_name`: 1 failed; restored 3 passed | `10-scripts/move_in_nineteen.sh` |

Sampled and already proved by their lanes (quoted in their records, not repeated): `customers/0080`
down-guard and RLS (SCHEMA), `deposit_releases` FORCE (RULINGS), `move_in_preferences` savepoint
(MONEY, since deleted with its catch), the Messaging hold-expiry test and `useMoveInEdit` (WIZ-REV),
`StepBilling` `onFirstBill` mutation (WIZ-BILL), the details view's three guards (DETAIL), the list's
three (LIST-UI).

### P3.02 · The 48 images beside the product

**Contact sheet: `08-qa/movein-2026-10-05/contact-sheet.html`** — each image beside its photograph
(`08-qa/movein-2026-10-05/after/p3/`, named as the image), every difference marked FIXED, RECORDED
(the lane's record cited), KIT (B14 rule 44), DATA (the walk database, not the product) or NEW.
47 photographed on 2.545.3 on one database; image 32 is paired with lane WIZ-UNIT's photo (no vacant
unit here has a last read). Each PNG was opened and checked non-blank.

**NEW, each filed first:** `DEF-CUS-9743` (the Service agreement default is listed and never queued;
its held ✕ says *Sent by default.*) · `DEF-CUS-9759` (What happened read *Messages 0 queued* —
**FIXED here, 2.548.1**, red first `{'queued': 1} != {'queued': 3}`, seen *1 queued* in the browser)
· `DEF-CUS-9761` (Billing's first Continue refused with nothing marked) · `DEF-CUS-9762` (Review's
Plan reads *None* while loading) · `DEF-CUS-9763` (a unit named without its unit number on the
list and the details view) · `DEF-CUS-9764` (request Documents columns) · `DEF-CUS-9765` (Unit &
reads: no Source column, device above sub-meter). None is in a money figure. 9761–9765 are left
open: 9763–9765 sit in lane MVI-FOLLOW's details-view files, 9761/9762 are small and are the next
WIZ-BILL/WIZ-REV touch.

**The coordinator's question on image 45, answered:** the Service agreement is NOT sent at
Complete — `notifications.move_in_message_plan` gives it `channels == []` by construction (no event
key), and *Messages* on a completed move-in lists the welcome, the receipts and no agreement. Its
✕ is disabled (it does nothing) with the hold reason *Sent by default.*, which is false for that
row. Two docstrings that claimed both defaults go out were corrected (`a34f527cc`, law 1). *Defaults
come from Settings · add any other* is the image's own words — a fact and an instruction, no
rationale — so it stays (B14 rule 33).

### P3.03 · Golden tests unchanged

`06-backend/tests/golden/`: **25 passed, 1 xfailed** (GT-8 late fee, xfail by design). No commit
since `f43fbdffe` touches the folder. G64: *document self-consistency: 33 checks … ENGINE-VERIFIED:
15 of 61 GTs … GT-1–11, GT-16, GT-24, GT-34, GT-47.* The first-bill tests (`test_us_bil_010`,
`8330`, `8331`, `5318`, `8563`, `oq530`, `6353`) are byte-identical to `f43fbdffe`.

### P3.04 · PostgreSQL proof of Complete, Cancel and Change date (law 14)

On PostgreSQL 16 (`config.settings.pgtest`), **74 passed, 0 skipped**: `test_cr171_p1_20_21_complete`,
`p1_22_cancel_move_in`, `oq_cus_12790_cancel_refund` (Nilesh's $150.00 + $25.00 = one $175.00
refund; a refused refund rolls the release back; the Work catch after the money keeps the money),
`mvi_flow_record_doors` (change date moves the account and its agreements, refused once billed,
meets the boundary-day rule), `p1_29_money_pg`, `deposit_releases_rls_pg`, `p1_01_rls_pg`,
`p1_14_first_bill_fees` and three first-bill suites. The cancel's savepoint was broken and went red
(P3.01).

### P3.05 · The nineteen, re-pointed to four steps

`Steps` now reads `step1_unit` (move-in date, reads) · `step2_customer` / `step2_contact` ·
`step3_billing` / `step3_deposit`; the report labels each field with step 1–3. `./10-scripts/
move_in_nineteen.sh`: **21 passed** (19 scenarios + 2 meta). The lane database (standing in for the
beta) counted before and after: service requests 10 · accounts 81 · payments 86 · journal lines
824 · readings 518 — unchanged.

### P3.06 · Every red line read and dated

Gates (`run_gates.py`, full, on 2.548.0 + this lane's work): **95 PASS · 45 FAIL · 2 SKIP**. Front end
(`vitest` over `features/customers`, `i18n`, `components`, `styles`): **3,362 passed · 4 failed**.
Back end: golden, the CR-171 PostgreSQL set, and every `test_cr171_*` plus the move-in suites on
SQLite (**292 passed · 2 failed · 21 skipped**, both failures below). Each red
that touches the move-in, dated with `git log -S`:

| Red | Move-in's? | Since | Done |
|---|---|---|---|
| G30 — `DEF-CUS-9729` marked fixed with no `fixed_commit` | yes | `102b31f2f` (2.540.1) closed without a commit | `fixed_commit` set → **G30 PASS** |
| G55 — commit `7da6b7c53` claims `DEF-CUS-9734` fixed, row open | yes | `7da6b7c53` (2.542.0) | verified fixed (*No opening read was recorded.*), row closed → G55's move-in claim gone (DEF-213, DEF-184 remain, older) |
| G53 — `customers/co_owner_models.py` says HUMAN-REVIEW-PENDING, no guard-list glob | yes | `6979a79cc` (2.526.0, SCHEMA) | joining the guard list is a PO ruling (`DEF-GOV-9710` precedent) — in §17.1 |
| G95 — `customers/move_fees.py` cites `tests/test_cr171_p1_13_move_in_payment.py`, which does not exist | yes | `bdb7b84ac` (2.529.0, MONEY) | 🔒 file — left for its review; reported |
| G98 — eslint: `moveDetail/AuditTab.dom.test.tsx:20` `_url`, `_opts` unused | yes | `39de596ba` (2.546.0, lane MVI-FOLLOW, running) | FOLLOW's file — reported, not touched |
| G6 — `customers/move_in_request.py:243` imports `apps.tenancy.models` | yes | `732573c28` (2.524.0, REQ) | G6 red on 57 older lines too; reported |
| vitest — `MoveEntryPoints.dom.test.tsx` first-occupant deposit case (`toHaveValue(150.00)`) | yes | `03e98c14e` (2.545.0, WIZ-BILL removed the deposit read) | filed `DEF-CUS-9769` |
| pytest — `test_cr171_p2_detail_reads::test_p2_10__…co_owners…` (the row gained `id`) | yes | `0e9b22d99` (2.543.0, WIZ-CUST widened DETAIL's pinned read) | filed `DEF-CUS-9770`, test re-pointed (the handle named, identifiers still refused) → 3 passed |
| pytest — `test_us_cus_004_tc1` expects `BR-CUS-017`, gets `BR-CUS-017 · BR-CUS-1047` | no | `eda8c9a14`, 2026-09-13 | older |
| vitest — ConfirmDialog census 39 ≠ 38 (`work/PartsPage.tsx`) | no | `368d908d7`, 2026-10-04 (`DEF-WRK-9721`) | older |
| vitest — `ReturnedPostBanner` refusal text | no | `DEF-CUS-9725` (filed by LIST-UI) | older |
| vitest — `wizardRailCensus`: rating's three tax-edit step lists | no | `b71588e74`, 2026-10-03 (CR-165) | older |
| G12 — `J-MVI-NINETEEN-…md` declares `id: JMVININETEEN` | the nineteen's journey | `fc084ed32`, 2026-09-19 | older |
| G106 — `OQ-CUS-12511` at `move_reads.py:1021` | no (the line quotes the retired id as history, `DEF-CUS-5937`) | 2026-09-19 | older |
| G5 SKIP — the isolation proof is stale | schema moved (incl. `customers/0080`, `payments/0047`/`0048`) | proof of 2026-10-02 | needs the 29-minute isolation run on PostgreSQL — not run here |

The other 37 failing gates name nothing in the move-in and are older than this CR (`G35` lists no
2.5xx version; `G135`'s reds are rating's base migration).

### P3.08 · Versions and rollback re-checked

Every CR-171 push carries its version in `CHANGELOG.md` and the three version files: 2.522.0,
2.524.0, 2.526.0–2.528.0, 2.529.0, 2.530.0–2.531.1, 2.532.0–2.548.1 (the gaps are other CRs'). The
rollback statement (§8.3) was incomplete and is amended below (`DEF-PAY-9760`).

### 17.1 · P3.07 material — every 🔒 file this CR touched, in plain words with its figure (for the coordinator; NOT sent)

Read from `12-governance/09-human-review-ledger.md` (rows of 2026-10-05) and the guard list. "Signed"
means the ledger already holds the PO's words for exactly what is said here.

| # | File(s) | What to say to the PO | State |
|---|---|---|---|
| 1 | `customers/migrations/0080…` + `co_owner_models.py` (schema, RLS) | *"A move-in can now hold Riya G as a co-owner (her SSN stored scrambled, staff see 9662), fees of $150.00 deposit + $25.00 connection, a text the day before move-in, and Kestrel Bakery LLC trading as Kestrel Bakery with PO-4471 on its bills. Undoing the change refuses while any of that exists, and says how many."* Also: may `co_owner_models.py` join the guard list? (G53 asks; the PO ruled the same question for three money files, `DEF-GOV-9710`.) | signed 2026-10-06 |
| 2 | `customers/move_fees.py` + `rating/move_in_fees.py` | *"Rosa moves in: $150.00 deposit + $25.00 connection + $40.00 same-day = $215.00, no tax. She pays $100.00 by check: $100.00 is held toward her first bill and $115.00 goes on it. Had she paid all $215.00, $150.00 is held as her deposit and $65.00 toward the fees. A typed fee figure that is not the code's saves nothing."* And the amendment: *"A plan charges Electric $12.00 and Water $8.00; Rosa takes Water only; the Base charge now reads $8.00 a month, not $20.00."* | signed 2026-10-06 |
| 3 | `billing/first_bill.py` (`move_in_fee_lines`, `_deposit_waived`) | *"Rosa's first bill shows the $25.00 and $40.00 fees once each, untaxed, plus her $150.00 deposit unless it was paid — and a deposit the clerk waived for hardship is no longer charged anyway."* (Golden tests and the first-bill tests unchanged — P3.03.) | signed 2026-10-06 |
| 4 | `customers/move_in_preferences.py` + `rating/discount_services.py`, `rating/services.py`, `rating/api.py`, `customers/discounts.py` | Signed (ruling 2): a billing clerk records the discount and the exemption certificate; *"the church pays $0.00 of the city tax, an account without the certificate $2.00."* **Then ruling (A) of the five (2.546.5, `DEF-CUS-9724`) changed this file again: "an exemption removes only its own tax — the church still pays $6.25 state tax on $100.00."** The ledger has no amendment row recording that ruling against `move_in_preferences.py` yet. | signed for ruling 2; ruling (A) recorded in the ledger 2026-10-06 (a ruling, not part of the six) |
| 5 | `customers/move_in_cancel.py` (cancel without a deposit) | *"Nilesh G moved into Unit 3B on 1 August and paid $25.00. Cancelling before any bill closes his account as of 31 July, ends water and sewer on 31 July, asks Finance to refund the $25.00, calls off visit WO-0062, keeps the readings, and the unit shows Vacant. Once a bill has gone out, Cancel is refused."* | signed 2026-10-06 |
| 6 | `payments/deposit_release.py`, `deposit_release_models.py`, `payments/0047`, `0048` | **Signed** (ruling (B), "Approve all four"): Nilesh's $150.00 deposit + $25.00 = one $175.00 refund to Finance, books DR 2300 / CR 2400 $150.00 dated the cancel day, no interest. **New from P3.08, to add:** *"Undoing the database change for deposit releases would delete the record that Nilesh's $150.00 was released while the books entry stays — so it must never be undone while a release exists; we will make it refuse, as the move-in tables already do."* (`DEF-PAY-9760`) | signed; the rollback sentence is new |
| 7 | `customers/service_request_service.py` (REQ buttons, Reopen, WIZ-UNIT P1.19) | *"A declined request SR-26-0014 can be reopened with a reason: same number, back to To approve, her documents kept, the decline kept in its history. No money moves."* No CR-171 ledger row exists for this file. | signed 2026-10-06 |
| 8 | `metering/connections.py` (`DEF-AST-9712`) | *"When a technician accepts the move-in read job on meter W-5000, the meter becomes Installed on that day if it was still in stock."* No money. No CR-171 ledger row exists for this file. | signed 2026-10-06 |

Nothing in this CR changes a signed money figure (B4/B5 untouched; golden 25 passed). The two
rows marked *no row* are a write-back gap, not a PO question: the coordinator adds them before review.

## 18 · Lane MVI-E2E-FIX record (R4, 2026-10-05) — version **2.549.0** (maintenance)

**What it fixed — the M1 defects of §17.3 plus `DEF-CUS-9758`** (commit `aadc44283`; decision log
*"MOVE-IN END-TO-END M1 FIXES"* holds the eight judgments; review-ledger row for the three guarded files).

| Defect | What a clerk sees now (M1, MVI-26-0008, on 2.549.0) |
|---|---|
| `DEF-BIL-9750` | The first-bill preview prices: sewer (a share of water) no longer waits for a read of its own; the preview asks the tariff, as the back-bill does. No rate or golden figure moved. |
| `DEF-CUS-9753` | The move-in reads *Completed* once E-M1 and W-M1 are read; the cart is not on *Still open*; RT-006 reads **13 short** (meters only), was 24. |
| `DEF-CUS-9752` | Step 1: Trash *Not metered* (TR-M1-1 is a cart). |
| `DEF-CUS-9754` | Check 2041 typed 10/10/2026 shows **10/10/2026** (was 10/09/2026) — midnight in the utility's zone. |
| `DEF-CUS-9756` | Search customer ID: Rosa owes **$84.20** ($50.00 + $34.20), was $0.00 — read back on this world. |
| `DEF-CUS-9755` | Billing tab: *Deposit taken $0.00 · $150.00 not cleared yet · Still to collect $0.00* (was *$150.00*). |
| `DEF-CUS-9749` | *Move-in completed*: *The deposit payment has not cleared.* (four warning codes, eleven languages, NATIVE-REVIEW-OWED). |
| `DEF-CUS-9757` | *Messages 2 queued* (email + letter); same root as `DEF-CUS-9759` (MVI-PROOF, 2.548.1), extended to count channels. |
| `DEF-CUS-9758` | A request row's `deposit: null` draws `—`. This branch's tab already used the null-safe cell (2.536.0); the crashing `MoveDepositCellView` (app-dev 2.531.2) is null-safe too. |

**Not touched:** `DEF-BIL-9751` (the first bill still carries the $150.00 deposit while check 2041 is
processing) — with the PO. **Filed, left:** `DEF-PAY-9771` (three more midnight-UTC writers),
`DEF-MET-9772` (the route/cycle *Meters* count still includes carts: *13 short of 24*).

**Proof.** Every new case red on the start tip `321aa53f6`, green after (14 backend, 3 frontend); the
15 money/read cases green on PostgreSQL 16; `tests/golden` green (G64 unchanged); G15 and G31 PASS.
**M1 re-run on 2.549.0, world restored from the post-`setup` dump: 112 PASS · 1 FAIL** — the one FAIL
is `DEF-BIL-9751`. Output and 17 photographs at 1440: `08-qa/movein-2026-10-05/e2e/M1-fix-2.549.0/`.
**Reds I did not cause (each red at `321aa53f6` before any change of mine):** 31 backend cases in 12
files (move-out scenarios, `test_w5_move_worklists`, `test_cr038_w7_write_modes`, `test_cr054_w1_reading_sheet`,
`test_us_ten_019_sample_records`, …) and three frontend files (`MoveEntryPoints`, `ReturnedPostBanner` =
`DEF-CUS-9725`, `wizardRailCensus` = `DEF-RAT-9348`).

## 19 · Lane MVI-E2E-1 record (R4, 2026-10-05) — P4.06–P4.11 (M2, M3), no version

**Test tooling only, so no version** (§17's precedent). **No product file was changed by this lane.**
Decision log *"MOVE-IN END-TO-END M2 + M3"* holds the five judgments. World built fresh on the lane's own
PostgreSQL 16 database with `cr171_e2e_matrix_world.py setup`, dumped once, restored before every run.
Run on build **2.549.0** (compose-mode bundle, API on the lane's own port), clerk Jo Ramirez, 1440.

**Runner additions** (`cr171_e2e_matrix_run.mjs`): `CASES.M2`, `CASES.M3`; step helpers `matchAndLink`,
`addCoOwner`, `addDocument`, `claimDiscount`; a case's `walkExtra` screens; step 3's *"$… goes on the first
bill"* sentence read; the check-number line asked only when a check was taken. **Readback additions**
(`cr171_e2e_matrix_readback.py`): `EXPECT.M2`, `EXPECT.M3`; payments read when *Add to bill* records
none or a part payment splits by purpose; the first bill's deposit line asserted as **plan − paid** (paid →
none, as M1; not taken → the plan's $150.00); `_case_extras` (co-owners, devices, discount enrolment,
account documents); `known_defects` labels an expected FAIL with its defect id, never hides it.

### 19.1 · M2 — Rosa Delgado, 300 Willow Court Apt 2B, MVI-26-0007, AC-2026-00057 — **104 PASS · 1 FAIL**

Passing, among the 104: Water and Sewer listed; opening reads asked for W-M2 and its sub-meter SW-M2 and
not for the backflow BF-M2 · *Search customer ID* finds Rosa by her SSN and shows **AC-2026-00054 $50.00 +
AC-2026-00055 $34.20 = $84.20** · Link → *Linked*; no second customer written; C-00052 now holds three
accounts · co-owner **Luis Delgado**, spouse, born 09/03/1977, responsible for bills, written and on the
move's Account tab · Fees **$175.00** (DEPOSIT $150.00 + CONN $25.00), not taxed; *"$175.00 goes on the first
bill."* · no payment recorded, no receipt queued · W-M2 121.5 **kgal**, SW-M2 42.0 **kgal**, committed
10/10/2026 · BF-M2 still under W-M2, no read · unit Occupied (derived), meters Installed (derived) · Still to
collect **$150.00** (the deposit not taken) · route, cycle, welcome queued (2), nothing sent.

| FAIL | Defect |
|---|---|
| The first-bill preview refuses: *"This connection's size is not recorded."* — W-M2 is 3/4" and its irrigation sub-meter SW-M2 is 5/8"; the size reader counts the sub-meter as a second claim and answers "unresolved". A bill run would refuse the same account. | `DEF-MET-9773` (high) |

### 19.2 · M3 — Harold Whitfield, 18 Juniper Street Unit 1, MVI-26-0007, AC-2026-00057 — **108 PASS · 0 FAIL**

Passing, among the 108: Electric and Gas; E-M3 8,905 **kWh**, G-M3 1,541 **ccf** · *New customer*, no match
block · *Assistance evidence* uploaded on step 2 and filed on the account (KYC folder, `cap-award-letter.pdf`)
· **CAP / low-income credit** claimed by the Billing Clerk and enrolled at Complete (PO ruling (b)), *Proof
pending* because CAP asks proof · Fees **$175.00** (a discount never waives a fee) · **$100.00 cash** is one
**prepay** payment, no deposit taken (never taken partly); *"$75.00 goes on the first bill."*; Still to collect
**$150.00** · the first-bill preview prices and carries the **$150.00** deposit and CONN $25.00, none taxable
· audit rows, balanced journals (the cash payment not yet journaled, printed).

### 19.3 · Each case's key check goes red

M2: `accounts_on_file` changed to expect AC-2026-00056 → *"LINKED: the returning customer holds her accounts on
file AND this one — expected [...00054, ...00056, ...00057], read [...00054, ...00055, ...00057]"*; restored → green.
M3: purposes changed to `("deposit", "100.00")` → *"the payments' purposes are as the rule splits them —
expected [('deposit', '100.00')], read [('prepay', '100.00')]"*; restored → green.

**M1 re-run with the edited runner (regression, world restored, not photographed): 113 PASS · 1 FAIL** — one
check more than §18 (each fee line on the first bill at its recorded amount); the FAIL is still `DEF-BIL-9751`,
now printed with its id (`known_defects`). **`DEF-BIL-9751` is not exercised by M2 or M3:** neither takes a deposit by check (M2 pays nothing, M3 pays
$100.00 cash below the deposit), so the deposit is rightly on both first bills. Output, red proofs and 36
photographs at 1440: `08-qa/movein-2026-10-05/e2e/M2/` and `M3/`.

## 20 · Lane MVI-POLISH record (maintenance, 2026-10-05)

Worked in its own worktree on PostgreSQL 16 database `sbh_wpolish` (`seed_demo`, `load_sample_data`,
the CR-171 seeds), backend 8747, front end 5747 (`vite build --mode compose`). Every fix red first,
quoted below.

### 20.1 · `DEF-CUS-9743` — the Service agreement default goes out (`2.549.1`)

* **Server.** `notifications.customer_events.queue_move_in_service_agreement` queues
  `contract_service_agreement` on the contract class's own channel (printed letter) through
  `queue_document`, keyed `uuid5(move record, "move-in-message:service_agreement")`, no event key.
  `customers.notifications_seam.queue_move_in_service_agreement` calls it inside its own savepoint
  (raises nothing, like the welcome); `services._move_in` calls it after the welcome and returns
  `service_agreement_message`; `move_in_complete.what_happened` counts it with the welcome.
  `move_in_message_plan` gives the row the channel the write will take (`["pdf_print"]`).
* **Missing template.** As the welcome: the row is written and holds at dispatch
  (`template_pin_unresolved` on the outcome). Review shows *No template* under the name.
* **Screen.** Review's row is ticked, *Printed letter*, *2 will send*; the held ✕'s *Sent by
  default.* is now true of both rows.
* **Red first.** On 381948c90: `assert [] == ['pdf_print']`; `AssertionError: Complete queued no
  service agreement`; `AttributeError: … has no attribute 'queue_move_in_service_agreement'`;
  vitest `expect(received).toHaveTextContent() received value must be a Node` (no *No template*)
  and `expected 2 to be 1` (willSendCount). Green: 3 passed (`test_def_cus_9743_…`), 16 passed
  (`MoveInMessages.dom.test.tsx`).
* **Blast radius, re-pointed.** `test_def_cus_6365…_goes_out_on_nothing` asserted the defect
  (`channels == []`) and now asserts `["pdf_print"]`; `test_cr048_b6_b10` counts the welcome and
  final-bill letters without the agreement and asserts the agreement separately; its seam count
  (red at base, `9 == 7`, two reads added since `dcc883047`) now names all ten entry points.
* **Judgments** (decision log, *"THE SERVICE AGREEMENT A MOVE-IN ALWAYS SENDS IS NOW QUEUED"*):
  paper, not image 45's *Email*; no template handled as the welcome; its own queue key.

### 20.2 · `DEF-CUS-9762` — Review's Plan says *Loading…*, never *None* (`2.549.2`)

`StepReview` draws `states.loading` (*Loading…*, `aria-busy`) in the Plan row while the unit's pricing
read is in flight; *None* stays for a unit whose read answered with no plan. **Red first** (a dom test
holding the read pending): `AssertionError: expected 'None' not to be 'None'`. Green: 11 passed
(`StepReview.dom.test.tsx`). No new catalogue key.

### 20.3 · `DEF-CUS-9763`, `9764`, `9765` — the details view and the list, as drawn (`2.549.3`)

* **9763 — a unit by number and label.** `metering.selectors.unit_refs` serves `unit_no` (same row, one
  query); `move_record_reads._unit_label` joins address · unit number · label (it read `unit_no or
  label` from a read that never served the number); the request view's unit fact and tile carry
  `unit_no`; the Move-ins list re-composes its Unit cell from one batched `unit_refs` read
  (`move_in_list._name_units_by_number`) and leaves the shared `_premise_cell` other tabs print alone.
  Screen: `moveDetailParts.UnitValue` — the number linked, then the label (images 03–17). **Red first**
  (base 381948c90): `assert '40 Kestrel Park · Unit 4A' == '40 Kestrel P...101 · Unit 4A'` (list) and
  the same for the view; vitest `Expected … SCW-U-311 · Unit 4A  Received: Unit 4A`.
* **9764 — image 21's table.** The kit's `DocumentTable` gains opt-in `neededLayout` (rule 43 — the
  request tab keeps the kit's table): Document · Needed (the *Required* chip, `—` otherwise) · File (the
  name opens it) · Added (date · who); no State, no Actions. NEEDED is the uploader's tick OR the
  tenant's move-in checklist (`checklist_required`), the capture page's two halves (`docRequired`).
  **Red first:** `expected [ Array(6) ] to deeply equal [ 'Document', 'Needed', 'File', …(1) ]`. One new
  key, `customers.moveDetail.documents.colAdded`, in all eleven catalogues.
* **9765 — order and Source.** `meterTreeOrder.readFirst` is now the ONE ordering helper for the meter
  tree, used by step 1 and the details view (what is read before what is not). `reads_for_unit` serves
  each head's `event_context`; the opening-read rows carry it as `event`; the tab's SOURCE column reads
  *Entered at move-in* (`move_in`), *Meter read* (any other read) or *Not read*. **Red first:**
  `expected [ 'W-5000', 'BF-0217', 'W-5000-S1' ] to deeply equal [ 'W-5000', 'W-5000-S1', 'BF-0217' ]`,
  the header list without *Source*, and on the server `KeyError: 'event'`. Three keys in all eleven
  catalogues (Italian uses *subentro*, `DEF-CUS-9747`).
* Green: backend 72 passed (the two new files plus the list, record page, detail, flow and request-view
  suites); vitest `moveDetail/` 35 + 3 + 1, `StepUnit` 13.

### 20.4 · `DEF-CUS-9769` and G98 — two test files, no version (test only, §17's precedent)

* **`DEF-CUS-9769`.** `MoveEntryPoints.dom.test.tsx`'s first-occupant case seeded the retired
  `deposit-standard` read and asked the old Deposit form for its Amount (red since `03e98c14e`,
  `expect(element).toHaveValue(150.00)`). Re-pointed, not deleted: it seeds `GET /move-ins/pricing`
  ONLY for the unit picked on step 1 (`u-new`, `moveInMoneyKeys.pricing`) and asserts the Fees table's
  *Security deposit* row reads **$150.00** — a step that asked about any other unit would read nothing
  and the case goes red, which is the interaction it pins (`DEF-CUS-6353` × `DEF-CUS-6369`). Green: 21
  passed.
* **G98.** `moveDetail/AuditTab.dom.test.tsx:20` — eslint `'_url' is defined but never used`, `'_opts'
  is defined but never used` (red since `39de596ba`). The mock's call shape is now typed on `vi.fn`'s
  generic, so `mock.calls[n][1]` keeps its type and nothing is unused. eslint clean; 3 passed.

## 21 · Lane MVI-E2E-2 record (R4, 2026-10-05) — P4.12–P4.17 (M4, M5), no version

**Test tooling only, so no version** (§17's precedent). **No product file was changed by this lane.**
Decision log *"MOVE-IN END-TO-END M4 + M5"* holds the six judgments. World built fresh on the lane's own
PostgreSQL 16 database (`sbh_we2e2`) with `cr171_e2e_matrix_world.py setup`, dumped once, restored before every
run; build **2.549.0** (compose-mode bundle, `/api` same-origin through `server.mjs` to the lane's backend on
8752), clerk Jo Ramirez (Billing Clerk), 1440.

**Built on lane E2E-1's hooks** (their `1770425c7`). **Runner:** `CASES.M4` and `CASES.M5` in their own
`Object.assign` block. New step helpers: `companyFields` (business type, Tax ID and state before *Search
customer ID*), `companyContact` (a new company's contact person) and `exemption` (step 3 *Tax exempt*:
category, number, issued, expires and the certificate PDF). `addCoOwner` is extended for `kind: "officer"`.
The walk gains generic checks: the account page's **title**, the unit's account line and each meter's
account line name the account HOLDER. A runner-side `knownDefects` labels a screen FAIL with its id.
**Readback:** `EXPECT_M4_M5`; the `co_owners` loop is extended for officers (title, share, signs).
`_exemption_extras` checks the certificate row, the blanket flag staying false (ruling (A)) and the PDF in
the KYC folder. `_first_bill_extras` checks fire as one line at $84.00, and the taxes by `tax_id`.

### 21.1 · M4 — Northgate Provisions LLC, 900 Commerce Row Suite 110, MVI-26-0007, AC-2026-00057 — **115 PASS · 5 FAIL**

Passing, among the 115:
* Step 1 lists Electric, Water, Sewer, Trash and Storm water. Opening reads are asked for E-M4 and W-M4 and
  not for the two carts.
* *Search customer ID* answers **found** by Tax ID 74-3051190 (*"Name and Tax ID match."*) and lists
  AC-2026-00056. Link gives *Linked*, and no second customer is written: C-00053 now holds AC-2026-00056 and
  AC-2026-00057.
* Owners **Hal Brennan**, Managing member, 60%, signs; **Priya Nandakumar**, Member, 40%.
* Fees **$325.00** (DEPOSIT $300.00 Commercial + CONN $25.00), not taxed.
* **Card 4417** $300.00 (deposit) + $25.00, receipts queued.
* E-M4 15,100 **kWh**, W-M4 642.0 **kgal**, committed 10/10/2026. The unit reads Occupied and the meters
  Installed (both derived).
* The first-bill preview prices every service: storm water base $2.00, trash 2 × 96-gallon cart $30.00.
  It carries all three taxes (State, County, City; the seed scopes the City tax everywhere), and no fee is
  taxable.
* Route RT-006, cycle, welcome queued, nothing sent.

| FAIL | Defect |
|---|---|
| The first bill carries the $300.00 deposit again (card recorded processing, exactly as a check) | `DEF-BIL-9751` (with the PO; not refiled) |
| Unit U-00007, meters E-M4 and W-M4, and the account page title name the account **"Hal Brennan"** (the contact person), not Northgate Provisions LLC | `DEF-CUS-9776` ×4 |

### 21.2 · M5 — Grace Fellowship of Cedar Ford, 12 Chapel Road Sanctuary, MVI-26-0007, AC-2026-00057 — **101 PASS · 6 FAIL**

Passing, among the 101:
* Water, Sewer and Fire are listed. Only W-M5 asks a read (89.5 **kgal**); the three fire lines are not
  meters.
* A new company, with no match block.
* The **Billing Clerk** records the **RELIGIOUS** exemption: CF-REL-2026-0412, issued 01/15/2026, expires
  12/31/2028, for the *City of Cedar Ford utility tax*. The certificate PDF is in the account's KYC folder.
  The account's blanket tax-exempt flag stays **false** (ruling (A)).
* Fees **$325.00**, not taxed. **Check 1187** $300.00 + $25.00.
* The first-bill preview has **Fire on ONE line, $84.00** (*"fire - 2 × Fire line 2", 1 × Fire line 6""*:
  $60.00 + 2 × $12.00). It has **no City tax**, and it **still** has TX State Utility Tax 6.25% = $13.13 and
  Local · Bexar County 2.00% = $4.20 on the taxable $210.10.
* The unit reads Occupied (derived). Route, cycle and messages as M4.

| FAIL | Defect |
|---|---|
| The first bill carries the $300.00 deposit again while check 1187 is processing | `DEF-BIL-9751` (with the PO) |
| Unit U-00008, meter W-M5 and the account page title name the account **"Ruth Okafor"** (the contact person) | `DEF-CUS-9776` ×3 |
| The account page reads *Tax exempt: No · Exemption reference —*; the certificate is nowhere on it | `DEF-CUS-9774` |
| The move's Billing tab reads **Tax: Taxed** for the exempt church | `DEF-CUS-9775` |

### 21.3 · Each case's key check goes red (`M4/m4-red-proof.txt`, `M5/m5-red-proof.txt`)

M5 has three red proofs:
* fire `84.00` → `85.00` gives *"the fire line is $85.00 — expected ['85.00'], read ['84.00']"*;
* fire expected on two lines gives *"fire is ONE bill line — expected 2, read 1"*;
* the State tax moved into `taxes_absent` gives *"the first bill carries NO TX State Utility Tax — ['Local ·
  Bexar County', 'TX State Utility Tax']"*.

M4 has two red proofs:
* `accounts_on_file` widened to a second account on file gives *"LINKED: … expected […00056, …00057,
  …00099], read […00056, …00057]"*;
* Hal Brennan's share 60 expected as 55 gives the officer check red.

Restored, both readbacks are green but for the labelled `DEF-BIL-9751`. The account-holder checks are their
own red/green pair: they PASS on M1 (*Avery Collins*) and FAIL on M4/M5.

**M1 re-run with the merged runner** (regression, world restored, not photographed): **117 PASS · 1 FAIL**,
four checks more than §19 (the account-holder checks, all passing). The FAIL is still `DEF-BIL-9751`.
**`DEF-MET-9773` is not hit by M4 or M5:** neither unit has a sub-meter, and both previews price. Output, red
proofs and 30 photographs at 1440: `08-qa/movein-2026-10-05/e2e/M4/` (16) and `M5/` (14).

## 22 · Lane MVI-FOLLOWUP record (maintenance, 2026-10-06) — version **2.549.4**

The proof follow-ups left after §20. Decision log *"MOVE-IN PROOF FOLLOW-UPS — THE WAIVE GLYPH, AND THE
THREE THINGS M3 NOTICED ABOUT DISCOUNTS"* holds the judgments.

### 22.1 · `DEF-CUS-9778` — a waive is a struck dollar, not a tick (`2.549.4`, `588617639`)

* **What was wrong.** §16 RULINGS-2 drew *Waive deposit* with `CommitIcon`, the tick the kit uses for
  commit / approve / verify. Beside $150.00 it reads as *paid* (M3 photograph `M3-3-billing.png`). B14
  rule 15 names no waive glyph and images 41–44 draw no waive, so the kit decides. The service
  request's fee *Waive* used the same tick.
* **What changed.** `components/icons.tsx` gains `WaiveIcon` — `DollarIcon`'s dollar struck through —
  and a *waive* row in its verb-to-glyph table. `moveInWizard/FeesTable.tsx` and
  `ServiceRequestDetailPage.tsx`'s fee row draw it. Not the ✕: the `TableArray` row's own *remove* is
  the ✕ in the same cell. *Undo waive* keeps `RollBackIcon`. No catalogue key, no behaviour change.
* **Red first** (the two dom tests now ask for `svg[data-icon="waive"]` inside the named button; old
  components): 5 failed, `expected null not to be null` (1 in `StepBilling.dom.test.tsx`, 4 in
  `ServiceRequestDetailPage.dom.test.tsx`). **Green:** 7 files, 164 passed (`moveInWizard/` and both
  request-detail dom files). `tsc --noEmit` clean, on the local install, after a planted error went red.
  eslint clean. G31 PASS.
* **Browser.** A Chromium render of the deposit row before and after, at 2×:
  `08-qa/movein-2026-10-05/after/waive/W5-waive-glyph-2.549.4.png`. ⚠ It is the row's markup with the
  kit's two exact SVG paths, not the booted product: the lane's PostgreSQL would not admit a login
  (peer and password auth both refused), so the full walk (`cr171_rulings2_waive_walkthrough.mjs`) was
  not re-run. The dom tests pin that the button named *Waive deposit* holds the waive glyph.
* **Rollback.** Redeploy `2.549.3` — screen only.

### 22.2 · M3's three discount observations, measured

| Observation | Verdict |
|---|---|
| The low-income evidence stays *Proof pending* until a System Admin checks it | **Intended** — ruling (2) of 2026-10-05 keeps verifying System Admin's, and `BR-RAT-076`'s default holds the reduction until proof is verified. **But** the uploaded letter is never attached to the enrolment, so the verifier hunts for it in the general KYC list: `DEF-CUS-9779` ⚠ **read `DEF-CUS-9780` — the register's id for this row (corrected 2026-10-06, §25)**, filed, left (two guarded money files and a proof-kind judgment) |
| The account page shows no discounts | **Defect, not built** — no drawing, no story: `DEF-CUS-9781`, filed, left (to be drawn and shown first) |
| *Municipal account* offered on a residential plan | **Defect, but not the one it looks like** — the plan carries Municipal on purpose (`CR-062` J2); the fault is that the claim list offers AUTOMATIC discounts at all (Municipal, Paperless, Autopay), which the nightly sync ends the next night: `DEF-CUS-9780`, filed, left (two guarded money files) ⚠ **ID CORRECTED 2026-10-06 (§25): the register files this fault as `DEF-CUS-9779`, and `DEF-CUS-9780` is the unattached evidence in the row above — fixed and closed as 9779 in `2.549.7`** |

### 22.3 · What is still unfinished in §20 and in §8's R3 rows

* **§20's six defects were fixed and left *open* in the register** — closed today: `DEF-CUS-9743`
  (`1d630bda8`, 2.549.1), `9762` (`bbf9e8ae1`, 2.549.2), `9763`/`9764`/`9765` (`0a6e5072d`, 2.549.3),
  `9769` (`524cfcb7f`, test only).
* **P3.07** (human review of the 🔒 files) is the one R3 task still open — now the sign-off lane's.
  §17.1's write-back gap (rows 7 and 8) and row 4's ruling-(A) amendment go with it.
* **`DEF-PAY-9760`** (found by P3.08) is still open: `payments/0047`'s down path does not refuse while a
  deposit release exists.
* **P2.37** is done but its eleven catalogues are NATIVE-REVIEW-OWED.
* Outside R3, still marked *open* in §8: P1.29 (each lane's PostgreSQL share), P2.35, P2.36 and P2.39
  (shares listed for WIZ-UNIT and WIZ-REV only), and P4's M1 tasks (P4.03–P4.05), M6, M7 and
  P4.24–P4.30.

## 23 · Lane TECH-COPY record (maintenance, 2026-10-06) — version **2.549.5**

Not move-in work; recorded here because this branch's lanes report into this file. **What was wrong:** a Field
Technician at the STAFF web app read only *"Sign in on the field app."* — on the sign-in page with *Field app* as a
plain line under it, and on the shell's 403 page as one small line and a small button on an empty page
(`DEF-IDN-9777`, follow-on to `DEF-IDN-9748`). **PO ruling 2026-10-06, verbatim:** *"this si correct - please
update - Field Technicians do not have access to the staff portal. Please sign in on the Field Technician mobile app
instead."* — an exception to B14 rule 33's six-word cap for this one message on these two screens only (decision log
of the same date; B14 rule 33 carries it).

* **Built:** `07-frontend/src/components/FieldAppNotice.tsx`, one component for both places — the two sentences and
  one primary **Open the field app** button (same destination as before, `/{tenant}/work/mobile/signin`; the shell
  still signs out first). The 403 page is now a centred card (`AuthCard`). Eleven catalogues, each in its own words.
* **Proof:** the two dom tests assert both sentences and the button by role, address and tier — proved RED on the
  old code first (3 failed of 11), green after (11 of 11); `tsc` clean (proved capable of failing); G15 and G31 PASS,
  Route B utility test 11/11. Photographs at 1440 by `10-scripts/def_idn_9777_field_app_notice_walkthrough.mjs`
  (11 PASS): `08-qa/def-idn-9777-2026-10-06/`.
* **Found on the way and filed, not fixed:** `DEF-GOV-9783` — G32/G33 never see this refusal key (raised through a
  named constant), so its length was never checked. And `render-checks/cr070-f-who-can-do-what.mjs` asserted
  "≤ 6 words" over a regex for the old sentence, which would have matched nothing and passed; it now asserts the
  two sentences.
* **Reds I did not cause, dated:** G33 — 10 refusals over the cap (e.g. `integrations.field.site_id`,
  `rating.schedules.bound_base_charge_code_*`), present in `en.json` by `63278ffc7` (2026-10-05); G13 — unwired
  props in `RateScheduleWizard.tsx` (`uomsPending`, since `7fb6de07e`, 2026-10-02) and `moveReadsCapture.tsx`
  (`readAtLabel`, since `ea9443712`, 2026-09-28).
* **Rollback:** redeploy 2.549.4; copy and layout only.

## 24 · Lane SIGNOFF-1006 record (2026-10-06) — the PO's sign-off on six 🔒 items of §17.1, no version

PO, verbatim: *"Money-file review: approve these six? - all good - go ahead"*. Decision log
*"SIX MOVE-IN MONEY FILES SIGNED"*. §17.1 rows 1, 2, 3, 5, 7 and 8 now read **signed 2026-10-06**; the
signature covers the six plain-English statements the decision-log row quotes verbatim, and nothing else.

* **Ledger** (`12-governance/09-human-review-ledger.md`, appended): four AMENDMENT rows (rows 1, 2, 3, 5 —
  the 2026-10-05 rows left as written) and two NEW rows (rows 7 and 8, which had none — the write-back gap
  this section's table named), each **RATIFIED 2026-10-06** on its statement. Docstrings keep
  `HUMAN-REVIEW-PENDING` (G7 requires it; the ledger row carries the state) — the 2026-10-05
  deposit-release precedent.
* **Row 4's ruling (A)** (`DEF-CUS-9724`, *"(a) An exemption removes only the tax named on its certificate.
  The church pays $6.25."*) now has its own ledger AMENDMENT row against `move_in_preferences.py`,
  recorded as a ruling already made, NOT as part of this signature; the file stays PENDING.
* **Not covered, still open:** whether `co_owner_models.py` joins the guard list (not asked); the
  typed-fee-figure clause of row 2 (offered in the ledger, absent from the statement shown); row 6's new
  rollback sentence (`DEF-PAY-9760`, not shown); the two credit-position reads beside the cancel; the RLS
  policy text; every other path of the six files.
* **Tests, red first:** eight sign-off tests beside each file's own fixtures (`test_the_statement_the_po_signed_on_2026_10_06`
  in the schema, first-bill, cancel, reopen and wiz-unit files; three `test_signed_2026_10_06__…` for row 2's
  three figures). Each failed against a one-line break of the code it guards — `'662' == '9662'`,
  `215.0000 == 115.0000`, `215.0000 == 0.0000`, `'20.00' == '8.00'`, a waived deposit billed, the close
  dated on the move-in, `'waiting_on_customer' == 'to_approve'`, `'inventory' == 'active'` — then the
  code was restored (`git diff` on `apps/` and `core/` empty) and the seven files plus the 9724 test ran
  **98 passed** on SQLite; the eight sign-off tests **8 passed** on PostgreSQL 16 (a UTF8 cluster — a SQL_ASCII one refuses the seed's `·` before any test runs).
* **Gates:** G7 before PASS (866 guarded files conform; 409 rows awaiting, 49 counted ratified by its
  blanket marker), after PASS, unchanged (its ratified count reads only the blanket marker, so the seven new rows do not move it). G53 before FAIL naming `customers/co_owner_models.py` and
  `work/raise_svc.py` (the same two since lane RULINGS-2, 2026-10-05 — not caused here, and the first is
  exactly the question left open above), after the same FAIL, the same two files — nothing added to the guard list, by design.

## 25 · Lane DEF-CUS-9779 record (maintenance, 2026-10-06) — version **2.549.7**

Decision log *"A MOVE-IN CLAIMS ONLY DISCOUNTS A PERSON APPLIES FOR"* holds the judgments.

* **What was wrong.** The Billing step's *Discounts* list was the plan's whole discount list, so a clerk
  could claim an AUTOMATIC discount — Municipal account (20% off), Paperless, Autopay. It was enrolled at
  Complete and the nightly sync (PO 2026-10-03 ruling (3)) ended it the next night. **Id note:** §22.2
  cited this as `DEF-CUS-9780`; the register files it as **`DEF-CUS-9779`** (9780 is the unattached
  evidence) — §22.2 is stamped, and this closes 9779.
* **What changed.** Rating: `discount_services.automatic_discount_ids(ids, day)` reads the version in
  force's stored `enrolment_mode`; `move_in_fees.narrowed_sections` adds `claimable_discounts` (the plan's,
  less the automatic ones) and leaves `discounts` whole for the plan panel. Customers:
  `move_in_preferences._claims` refuses an automatic claim per row as `discount_claims[i].discount_id`,
  key `customers.moveIn.discountAutomatic` — *"This discount is applied automatically."* (5 words, a
  fact; all eleven catalogues). Screen: `StepBilling.tsx` passes `claimable_discounts` to the list. No
  rate, value or nightly-job change; the sample residential plan keeps MUNICIPAL (`CR-062` J2).
* **The drawing.** The mock-up draws *This customer can claim: Autopay · Paperless*; that clause is put
  to the PO on the PENDING ledger row rather than built (decision log (4)).
* **Blast radius.** Plans & Rates' *+ Enroll an account* and `POST /accounts/{id}/discounts` accept an
  automatic discount the same way — **`DEF-RAT-9792`, filed, left** (a second screen and a round-2 test
  that claims an automatic programme on purpose). The request path's claim block
  (`moveInRequestBlocks.tsx`) already lists only Senior / Low income / Veteran. The account page shows no
  discounts (`DEF-CUS-9781`); the portal has no claim surface.
* **Red first.** Backend, 4 new cases on the pre-fix code: 3 failed on SQLite and the same 3 on PostgreSQL 16 (`DID NOT RAISE ValidationError` for the Municipal claim, `KeyError: 'claimable_discounts'`, `AttributeError` — no `automatic_discount_ids`), run in a detached worktree of the pre-fix tip
  (the fourth — a claimed SENIOR still enrols — passes before and after, as it should). Front end:
  `StepBilling.dom.test.tsx` *the claim list offers only Low income* failed on the old wiring with
  `expected [ Array(3) ] to deeply equal [ 'Low income' ]` (Autopay, Municipal account offered).
* **Green.** SQLite: the new file + `test_cr171_p1_15_move_in_preferences.py` +
  `test_cr171_p1_12_move_in_fees.py`, 37 passed. PostgreSQL 16 (`config.settings.pgtest`): the new file + `test_cr171_p1_15` + `test_cr171_p1_29_money_pg.py` + `tests/golden`, **44 passed, 1 xfailed** (the golden suite's own declared xfail), none skipped — golden unchanged and green. vitest `moveInWizard/` 5
  files, 67 passed. `tsc --noEmit` clean on the local install after a planted error went red. G7, G15,
  G31 PASS; my key is in neither G32's nor G33's list (their reds, and G13's, predate this lane — e.g.
  G13's `readAtLabel` dates from `ea9443712`, 2026-09-28).
* **M3 (Harold Whitfield) re-run** through `cr171_e2e_matrix_run.mjs` on 2.549.7 (lane PostgreSQL 16,
  world restored from the matrix dump, compose bundle, API on the lane's port), with a new runner check
  *the Discounts list offers no automatic discount*: **112 PASS · 1 FAIL.** The list read *Choose a
  discount | CAP / low-income credit*; CAP enrolled *Pending*. The one FAIL is *the sub-type is the one
  the clerk picked — expected 'senior_low_income', read None*: the customer step's photograph shows
  *No sub-category*, so the runner's sub-type pick did not take — the customer step, not this change
  (108 PASS · 0 FAIL on 2.549.0 per §19.2; not chased here). Photographs at 1440:
  `08-qa/movein-2026-10-05/after/discounts-9779/M3/` — `M3-3-discounts.png` (the list),
  `M3-3-billing.png` (the whole step) and the walk's other screens.
* **Rollback.** Redeploy `2.549.6` — no migration.

## 26 · Lane MVI-DEPOSIT-9751 record (maintenance, 2026-10-06) — version **2.549.6**

**What was wrong.** The move-in wizard records every counter payment as still processing, and the
first bill's deposit read counted only cleared deposit money. So a deposit paid at move-in by check
or card was billed a second time on the first bill: M1 paid $175.00 by check 2041 and was billed
$150.00 again; the church (M5) paid $325.00 by check 1187 and was billed $300.00 again.

**The ruling built.** PO 2026-10-06, option (a) (decision log, top row): a deposit taken at move-in
counts as paid straight away, whatever the tender; a later bounce or reversal puts it back through
the process that already exists. BR-BIL-012 amended (CONFIRMED 2026-10-06).

**What changed (two reads in payments, no migration).**
* `deposit_release.deposit_counted_paid` (new) — deposit money cleared OR processing, net of returns
  and releases. It is what `credit.deposit_payments_for_account` (billing's only reader) now serves,
  so the first bill and the one-time preview stop billing it.
* `deposit_release.deposit_still_held` — what a release (and the refund after it) may pay out —
  still counts cleared money only. Judgment in the decision log row *"`DEF-BIL-9751` BUILT — WHICH
  READ COUNTS A PROCESSING DEPOSIT, CALLER BY CALLER"*.
* Both now exclude a check voided at the counter (`failed`): `DEF-PAY-9782`, found reading the
  callers — a voided $150.00 deposit check still read as held and could have been refunded.
* Move's Billing tab unchanged: *Still to collect* already read $0.00 (`DEF-CUS-9755`); *not cleared
  yet* stays true. Only stale comments moved.

**Owed again, through existing paths only (tested):** processing check cancelled → $150.00 deposit
line again; cleared check bounced (NSF reversal) → $150.00 again; check voided → $150.00 again, held
$0.00. **Stated, not built:** once the first bill has ISSUED without the line, a later bounce shows the
deposit as still to collect on the move but no later bill carries a deposit line (BR-BIL-012 makes it
a first-bill line; billing it elsewhere would be a new path).

**`DEF-CUS-9789` (lane MVI-E2E-3, Cancel move-in refunds nothing while the counter money is
processing) is NOT changed by this lane and stays open.** This fix deliberately keeps the release on
cleared money, so a processing deposit is still not released or refunded on cancel — that is the rule
that a refund never pays out money that has not arrived. The honest answer for uncleared money on a
cancelled move-in is probably to CANCEL those payments (the existing processing-payment Cancel,
which writes a reversing row and pays nothing out) rather than to refund them; that is a change to the
cancel flow, not to this read, and is left for its own lane.

**Proof.**
* `tests/test_def_bil_9751_move_in_deposit_counts_paid.py` — 5 cases; 4 RED on the old code
  (check and card billed $150.00 again; the returned-check case; the voided check held $150.00), all
  green. Neighbours + golden on SQLite: **203 passed, 7 skipped, 1 xfailed**. On PostgreSQL 16 (golden,
  this file, the cancel-refund file, `DEF-CUS-9755`'s file): **44 passed, 1 xfailed**.
* Matrix re-run on 2.549.6, fresh world on PostgreSQL 16, 1440, clerk Jo Ramirez:
  **M1 118 PASS · 0 FAIL** (was 117 · 1); **M5 102 PASS · 5 FAIL** (was 101 · 6). The deposit check
  passes on both. M5's five FAILs are other lanes' filed defects (`DEF-CUS-9776` ×3, `9774`, `9775`);
  two of the 9776 lines print without their label because M1 ran first in the same world, so the
  church's account number is AC-2026-00058 rather than the labelled 00057. Output and photographs:
  `08-qa/movein-2026-10-06/def-bil-9751/M1/`, `M5/` (`M5-w5-billing.png`: *Still to collect $0.00*,
  footer v2.549.6).
* `cr171_e2e_matrix_readback.py`: the `DEF-BIL-9751` known-defect label removed from M1, M4 and M5
  (a fixed defect must not label a regression). M6's label is MVI-E2E-3's in-progress work and was
  left for that lane.
* **Rollback.** Redeploy the previous build — no migration.

## 27 · Lane E2E-FIX-2 record (maintenance, 2026-10-06) — version **2.549.8**

**What it fixed — §21's three screen defects** (decision log *"AN ACCOUNT IS NAMED BY ITS CUSTOMER, AND ITS
EXEMPTION IS READ FROM ITS CERTIFICATES"* holds the five judgments). Worked in its own worktree on PostgreSQL 16
database `sbh_wname` (`cr171_e2e_matrix_world.py setup`, dumped once, restored before every run), backend 8791,
front end 5791 (`vite build --mode compose`), clerk Jo Ramirez (Billing Clerk), 1440.

| Defect | What a clerk sees now (on 2.549.8) |
|---|---|
| `DEF-CUS-9776` | A company's account is titled by the company: M5 *Grace Fellowship of Cedar Ford* (was *Ruth Okafor*), M4 *Northgate Provisions LLC* (was *Hal Brennan*) — on the account page title and Customer › *Full name*, the unit's account line and each meter's. The global search finds the account by the company's name. A person's account reads as before. |
| `DEF-CUS-9774` | M5's account, Account setup: *Tax exempt · Exempt from City of Cedar Ford utility tax · Exemption reference · CF-REL-2026-0412 · Exemption expires · 12/31/2028* (was *No · — · —*). The unit's Account tab reads *Claimed*. |
| `DEF-CUS-9775` | MVI-26-0007's Billing tab: *Tax · Exempt from City of Cedar Ford utility tax · CF-REL-2026-0412 · until 12/31/2028* (was *Taxed*). |

* **One source each.** The name: `customers.selectors.primary_contact_name` and every plural of it (the batched
  read, the bulk-check prime, the list's sort subquery, the search popover) — the current customer's
  `display_name`, the contact's only where no current customer holds the account. The front end's
  `accountHeadline` now reads the server's `name` first. The exemption: `rating.selectors.
  exemption_certificates_for_account` → `customers.seams.account_tax_exemptions` → the account detail's new
  `tax_exemptions`, read by ONE component (`AccountTaxExemption.tsx`) on both screens. One new key,
  `customers.account.exemptFrom`, in all eleven catalogues (NATIVE-REVIEW-OWED).
* **No data correction.** No account row stores a name; the contact and the customer were written right at
  move-in. Bills already issued keep the name frozen into them (hard rule 4); new bills are addressed to the
  company.
* **Filed, not fixed (same roots, other modules):** `DEF-CWP-9795` (the customer portal's *Your account* reads only
  the blanket flag), `DEF-INT-9796` (the partner Customers API names a company by its contact).
* **Red first.** Backend (`test_def_cus_9774_9776_account_name_and_exemption.py`, base `6e7ff85be`): 6 failed —
  `assert 'Ruth Okafor' == 'Grace Fellow...of Cedar Ford'`, `KeyError: 'tax_exemptions'`; green: 6 passed. Front end:
  `AccountDetailPage.test.tsx` *expected 'Ruth Okafor' to be 'Grace Fellowship of Cedar Ford'* and no *Exempt from*;
  `BillingTab.exemption.dom.test.tsx` *Unable to find … Exempt from City of Cedar Ford utility tax · CF-REL-2026-0412*;
  green: 3 + 3 passed. `tsc` clean (proved capable of failing with a planted error); eslint clean; G15, G31 and
  `routeBUtilities.test.ts` PASS.
* **Matrix re-run** (runner: the five `knownDefects` labels removed, two checks added — *the account says Exempt from
  the City's tax* and *the move's Billing tab says Exempt from the City's tax*). First on this lane's own build before
  the rebase: M4 119 · 1, M5 108 · 1, M1 117 · 1, each FAIL `DEF-BIL-9751`. **Then on the pushed tip, build 2.549.8,
  which also carries §26's `DEF-BIL-9751` fix: M4 120 PASS · 0 FAIL** (was 115 · 5), **M5 109 PASS · 0 FAIL** (was
  101 · 6), **M1 regression 118 PASS · 0 FAIL**. Output and 30 photographs at 1440:
  `08-qa/movein-2026-10-05/e2e/M4-fix-2.549.8/` and `M5-fix-2.549.8/`.
* **Blast radius, re-pointed (two tests).** `test_br_cus_068_tc6` asserted a master account is NAMED by its contact
  (*Dana Whitfield*); it is now named by its owner customer (*Whitfield Rentals LLC*) and the contact is asserted
  separately. `test_t2_9b` counted ONE `customer_accounts` read per account-list page; it is now TWO (the number and,
  new, the name) — still constant however many rows. 45 test files that read a name or an exemption were run on base
  `6e7ff85be` and on this change: those two were the only differences; the other 32 reds were red at base (the
  `accounts.account_type_id` NOT NULL fixture in the search and list suites, the connector registry, the move-out
  flow). Front end: `features/customers` 2,382 passed; its two reds (`ReturnedPostBanner` = `DEF-CUS-9725`,
  `wizardRailCensus` = `DEF-RAT-9348`) are §18's. G13 is red at base on `RateScheduleWizard` (`7fb6de07e`,
  2026-10-02) and `moveReadsCapture` (`ea9443712`, 2026-09-28), not this lane's.

## 22 · Lane MET-9773 record (maintenance, 2026-10-06) — `DEF-MET-9773` fixed, version **2.549.9**

**What was wrong.** M2's first bill could not be priced. Rosa Delgado's main water meter W-M2 is 3/4" (`W-34`) and
her irrigation sub-meter SW-M2, under it on the same connection, is 5/8" (`W-58`). The size reader
(`metering.selectors.connection_size_for`) took every asset on the connection as a claim on its size, saw two,
and answered *unresolved* — so the preview refused *"This connection's size is not recorded"*, and a bill run
would have refused her too. Every caller goes through that one function (the bill run, the first-bill preview,
the move-in's Billing step, deposit-by-size, the rate card's minimum), so the fix is in one place.

**What changed** (🔒 `06-backend/apps/metering/selectors.py`, HUMAN-REVIEW-PENDING, review-ledger row of
2026-10-06). The size is read from the connection's MAIN meter(s): an asset whose parent stands on the same
connection — a sub-meter or a device under a meter — no longer takes part. One helper,
`_connection_top_assets`, now feeds the size, the meter the bulk Check names when there is no size, and the meters
the Check's inline *set size* writes to, so the three cannot drift. **Kept:** two main meters with different sizes
still refuse by name (`test_def_1900_connection_size.py::TC8`, green). **The judgment** (decision log
*"THE MAIN METER SIZES THE CONNECTION"*): a sub-meter whose parent is on ANOTHER unit — an apartment submetered off
the building's master — is the top of its own connection and still prices that unit. No rate, price or signed
figure moved; trash and fire (counted per asset through `billable_size_groups`) are untouched.

**Proof.** (Unit and suite runs were taken on start tip `6e7ff85be` plus this fix.) `tests/test_def_met_9773_submeter_size.py` — four cases. Red first on the start tip: `assert None ==
'W-34'` (main 3/4" + sub 5/8") and `assert 'W-58' is None` (an unsized main took its sub-meter's size); the
two-different-mains and submetered-apartment cases green before and after. Green after, with 101 neighbouring size,
fire, trash, deposit-by-size and rate-card cases (105 passed, 16 skipped on SQLite), `tests/golden` green and
unchanged, and the new file plus `test_def_1900_connection_size.py` green on PostgreSQL 16 (`config.settings.pgtest`).

**M2 re-run end to end on 2.549.9** (`e43a59db4`, the branch tip with this fix; fresh world on the lane's own PostgreSQL 16 database, gunicorn + `server.mjs`,
clerk Jo Ramirez, 1440): **113 PASS · 0 FAIL** (the case has 113 checks now, not §19.1's 105 — §21's runner added
the account-holder checks). The first-bill preview prices: water usage tier 1 $12.72 · water base **$15.00** (the
3/4" base) · sewer usage $9.00 · sewer base $9.00 · security deposit $150.00 · connection charge $25.00 · Tax Local
$0.91 — **$221.63**. The asset page shows *Connection size: Water 3/4"* on W-M2. Output and photographs:
`08-qa/movein-2026-10-05/e2e/M2-2.549.9/`. The readback's `known_defects` label for M2 is emptied (nothing is
expected to fail; the key stays because P25 spreads it).

**The runner had a race, found by re-running** (`DEF-MET-9802`, fixed in `e43a59db4`, test tooling): the
sub-type was picked only if its list had already loaded, so in 2 runs of 4 on one build the pick was skipped
silently and the readback read the sub-type as None. It now waits up to 8 seconds for the list. (A second race —
a screen read before its heading was drawn — showed in the same runs and had already been fixed by lane
MVI-E2E-3's `visit()` wait on the tip.) The 2.549.0 runs had simply won the race.

**A red this lane did not cause** (`DEF-BIL-9801`, filed): `test_def_rat_8004_one_version_per_date.py` cases
`test_4f` and `test_4g` are red on the start tip `6e7ff85be` with no change of this lane applied (run in a separate
worktree) — they expect the hold reason `plan_has_no_tariff_for_service` and the product gives
`connection_size_unresolved_for_sized_schedule`. Their subject is an unsized main meter with no sub-meter, which
this fix does not touch. Also red identically with and without this fix, on PostgreSQL 16 under
`JOBS_EAGER=false` (not filed — it may be this lane's environment rather than the product):
`test_oq_1361_fire_lines_and_no_net_meter_pg.py`'s fire ($0.00 for $84.00) and solar ($0.00 for $168.00) cases.
Tier-1 gates: G53, G67 and G106 red, each naming files this lane did not touch.

**Rollback:** redeploy `2.549.8`. No migration and no data written; a read only.

## 28 · Lane MVI-E2E-3 record (R4, 2026-10-06) — P4.18–P4.26 (M6, M7, cancel, change date, the request path), no version

**Test tooling only, so no version** (§17's precedent). **No product file was changed by this lane.** Decision log
*"MOVE-IN END-TO-END M6, M7, CANCEL, CHANGE DATE, REQUEST PATH"* holds the judgments. World built fresh on the lane's own
PostgreSQL 16 (`sbh_we2e3`, port 55473) with `cr171_e2e_matrix_world.py setup`, dumped, restored before every run; final
runs on build **2.549.9** (compose-mode bundle behind `server.mjs`), clerk Jo Ramirez (Billing Clerk), 1440. Every FAIL is
a filed defect, labelled in the output; every key check was broken in memory and seen red, then green
(`10-scripts/cr171_e2e_matrix_red_proof.py`, one `*-red-proof.txt` per case). Output, red proofs and 112 photographs:
`08-qa/movein-2026-10-05/e2e/M6/`, `M7/`, `P24/`, `P25/`, `P25B/`, `P26/`. **M1 re-run with the extended runner
(regression, world restored): 118 PASS · 0 FAIL.**

**Tooling added.** World: a `requests` command (two move-in requests, To approve, on two new vacant units — P4.26 only),
and the City tax also reaches **Municipal** accounts (see M7). Runner: `CASES.M6`, `M7`, `P24`, `P25`, `P25B`, `P26`;
`worldCase` (a copy of M1/M2), `after` (an act on the details view), `run` (a request path), `leaveUnread`, `offers`,
`poNumber`; Complete's warnings printed with their server detail; the first bill's lines printed; a second field visit
picks from ITS OWN list (the unscoped match picked row 1's hidden option — never exercised before M6); a slow page waits
for its heading before it is read. Readback: `EXPECT_M6_M7`, `--after cancel|date|requests`, `--was` (proration's
before-figure), solar / trash-count / PO / services-absent bill checks.

### 28.1 · M6 — Foundry Works Fabrication Inc., 5 Foundry Way Bay 3, MVI-26-0007, AC-2026-00057 — **125 PASS · 3 FAIL**

Passing, among the 125: Electric, Gas, Water and Solar listed; opening reads asked for E-M6, G-M6 and W-M6, not for the
inverter PV-M6, which still stands behind E-M6 · a new company (no match block), contact Dale Mercer, and the account,
unit and meters are named after the company (`DEF-CUS-9776` fixed) · Fees **$525.00** (Industrial deposit $500.00 +
CONN $25.00), not taxed · **$525.00 cash**: two payments, still *processing* (the wizard records cash as it records a
check), and the first bill does **not** carry the deposit again (`DEF-BIL-9751` fixed) · first bill: electric base
$630.00 + usage $127.50, gas $10.56 + $97.75, solar $112.00, water $63.75 + $44.20, CONN $25.00; State 6.25% $70.81 and
County 2.00% $22.66 on $1,133.01; no City tax (not an industrial class) · route, cycle, messages queued.

| FAIL | Defect |
|---|---|
| Two visits booked on step 1 (Opening read on E-M6, Reconnect visit on G-M6) — 0 work orders raised. Both templates are the sample set's WATER templates; Work refuses them on an electric and a gas meter, and Complete drops both | `DEF-WRK-9784` (high) |
| Move-in completed prints the raw code `work_orders_not_raised` | `DEF-CUS-9785` |
| The first bill charges **sewer** ($38.25 usage + $9.00 base, and taxes them) to an account that never started sewer | `DEF-BIL-9793` (high, money) |

### 28.2 · M7 — Cedar Ford Independent School District, 77 School Lane Main campus, MVI-26-0007, AC-2026-00057 — **100 PASS · 4 FAIL**

**Government · Schools cannot be entered**: `government` is a legacy category no form may pick (BR-CUS-094) and Schools
hangs under it (`DEF-CUS-9786`; its root, Settings unable to clear the legacy flag, is `DEF-CUS-9808`). M7 was therefore
entered as **Municipal**, no sub-type, and the world's City tax was widened to Municipal so the GOVERNMENT certificate has
a tax to remove (judgment (2) below). Passing: Water, Sewer, Trash; W-M7 read 1,462.0 **kgal**, the three carts not
meters · the **Billing Clerk** records the GOVERNMENT exemption CF-GOV-2026-0077 (issued 07/01/2026, expires
06/30/2027) for the City tax, the letter filed in the KYC folder, the blanket flag false · **Add to bill**, no payment,
*"$25.00 goes on the first bill"* (no deposit rule for this class; CONN $25.00) · the PO **PO-2026-118** typed on step 2,
shown on Review and stored on `accounts.po_number` · first bill: trash **3 × 96-gallon cart $45.00**, water $68.00 +
$93.60, sewer $9.00 + $81.00, CONN $25.00; **no City tax** (the certificate), **no State tax** (not this class), County
2.00% **$5.93** on $296.60 · the account page and the move's Billing tab show the certificate (`DEF-CUS-9774`/`9775`
fixed).

| FAIL | Defect |
|---|---|
| Step 2 does not offer Government (the PO's M7: Government · Schools) | `DEF-CUS-9786` |
| The first bill carries no PO — nothing in billing reads `accounts.po_number` | `DEF-BIL-9787` |
| The account page and the move's Account tab never show the PO | `DEF-CUS-9788` ×2 |

### 28.3 · P4.24 — Cancel on a copy of M1 — **128 PASS · 4 FAIL**

**Cancel is offered on *Scheduled / Waiting on a read* only, never on *Completed*** (the PO's actions table, decision
log *"DETAILS-VIEW ACTIONS BY STATUS RULED AS PROPOSED"*): a first try with both M1 reads taken read *Completed* with
*More ▾ Send a message, Print* and no Cancel — as ruled. So the copy reads E-M1 only and leaves W-M1 for its booked
Opening-read visit (step 1 lets a read go blank only when a visit will take it). Avery Collins paid **$175.00 by check
2041** (deposit $150.00 + CONN $25.00). *Cancel move-in…* listed *"Account AC-2026-00057 closes. WO-0053 canceled. The
unit is vacant again."*; after the press the move reads **Canceled**. Read back and on screen (PASS): account closed on
**10/09/2026**, the day before it opened; four agreements ended that day; WO-0053 canceled; E-M1's opening read kept;
the unit reads **Vacant** and is offered again on a new move-in; the two payments untouched; audit written.

| FAIL | Defect |
|---|---|
| No refund line in the modal; no refund request; no deposit release; nothing on the account's Payments tab — the **$175.00** stays with the utility on a closed account (J6 / `OQ-CUS-12790` (a) worked figure: ONE refund of $175.00) | `DEF-CUS-9789` ×4 (high, money) |

`DEF-CUS-9789` meets lane MVI-DEPOSIT-9751's judgment (§26): a release still draws on CLEARED money only, so a cancel
before the check clears refunds nothing; §26 suggests cancelling the processing payments instead. **That collides with
the PO's own worked figure for `OQ-CUS-12790` (a) — Nilesh, $175.00 by check, cancelled, one $175.00 refund — and is
the coordinator's to put, not this lane's.**

### 28.4 · P4.25 — Change move-in date 10/10/2026 → 10/15/2026 — copy of M2 **121 PASS · 3 FAIL**, copy of M1 **113 PASS · 3 FAIL**

Change date is offered on *Waiting on a read* only, so each copy leaves one register for its visit (SW-M2; W-M1). After
*Change date ✓* (PASS, both): the account opens **2026-10-15**, every agreement starts that day, the move record keeps
its own date (never updated), audit written, the account page reads 10/15/2026, and **the first bill's prorated base
moves**: M2 **$24.00 → $20.13**, M1 **$48.00 → $40.26** (26 of 31 days). The "before" figure is the first bill priced
before the change: after it, a preview "from 10/10" prices from the account's new start and would compare a figure with
itself (seen once: $40.26 → $40.26 — the check was rewritten and that pair kept as its red proof). The M1 copy was added
while `DEF-MET-9773` kept M2's first bill from pricing; it is kept as a second witness now that M2 prices (2.549.9).

| FAIL | Defect |
|---|---|
| The details view's *Moved in* chip and *Moved in on*, and the Move-ins list, still read **10/10/2026** — also after a reload (server reads `move_records.effective_on`) | `DEF-CUS-9790` ×3 per copy |

### 28.5 · P4.26 — the request path — **32 PASS · 0 FAIL**

SR-26-0009 (Maya Okonkwo → U-00011, 21 Lantern Way) reads *To approve* → **Ask for more…** (*"Please send a copy of your
lease."*) → *Waiting on customer*, the ask queued to the applicant, never sent → **Approve ✓** → *Not started* → **Start**
opens the four-step form from the request on U-00011 → Complete (W-R1 97.5 kgal, Add to bill, *"$175.00 goes on the first
bill"*) → MVI-26-0007, the job **done**, the account opened on the request's start **2026-10-12**, and the move names its
request. SR-26-0010 (Victor Hale) → **Decline…** with a reason → *Declined*, reason kept, refusal letter queued, no job,
no account; its Messages tab lists the letter.

### 28.6 · P4.27–P4.29

Read back in every case above (units, meters and devices; fees, payments, receipts, audit, balanced journals with the
not-yet-journaled count printed; route, cycle, work orders, messages). **Not exercised:** a meter set from stock and its
visit accepted (In stock → Installed, `BR-AST-020`) — no case sets a meter, so that half of P4.27 stays open.

## 29 · Lane DEF-WRK-9784 record (maintenance, 2026-10-06) — version **2.549.13**

Two defects M6 found (§28.1): **`DEF-WRK-9784`** — the Field visit offered visit templates of another service and
Complete then raised no work order at all — and **`DEF-CUS-9785`** — *Move-in completed* printed the raw code
`work_orders_not_raised`. Both **fixed** in `77f00cd6b`, build **2.549.13**. Judgments: decision log *"A MOVE-IN'S
VISIT IS RAISED ON ITS METER'S SERVICE OR REFUSED BY NAME BEFORE SAVE"* (2026-10-06).

**Why Complete raised none.** The sample set seeded its six visit templates for the tenant's FIRST metered service only
(water), so M6's *Opening read* (E-M6) and *Reconnect visit* (G-M6) were water's. Work refused each on its meter
(`work.order.template_wrong_service`); the rows are raised in ONE savepoint, so both were lost; `_raise_flow_work`
caught it, completed the move and kept only a warning — nothing reached the server log.

**What changed.** Step 1: a row's *Work order* list is its *For* meter's service (the whole offer, each entry naming its
service, when no meter is set); a pick that no longer fits the meter is swapped for the same visit of the meter's
service, or refused on the row (*Template is for another service.*) and Continue holds. Server: the same check runs
before the move-in is written (`from_flows.check_order_rows_on_unit`, also on the move's *Add work order*); a typed row
on a meter never borrows another service's template; a failed raise is logged on `smartbillhub.customers`. Sample set:
the six visit templates per metered service (water keeps ST-0019…; electric and gas get their own). Screen:
`warningText` falls back to a warning's own `message_key` — also fixes `work_order_not_assigned` /
`work_order_not_scheduled`. No new catalogue string, no migration, no money.

**Proof.**
* Red first, then green. Backend `tests/test_def_wrk_9784_visit_template_service.py` on **PostgreSQL 16** — unfixed
  code **4 failed · 2 passed** (did not raise; 0 orders raised; nothing logged; electric had no *Final read*), fixed
  **6 passed**. Front end `fieldVisitServiceScope.dom.test.tsx` — unfixed **7 failed · 1 passed**, fixed **9 passed**.
* Neighbours on PostgreSQL 16 (wiz-unit server, fix8b, first-occupant move-in, US-WRK-039, flowfix, srv4, DEF-CUS-6487,
  flow record doors): **72 passed · 1 failed** — the failure is
  `test_us_wrk_039_from_flows::test_def_wrk_3725_the_move_out_field_visit_is_on_step_2_not_step_4`, a source scan for a
  `shortfall` step that `e45a8e034` (2026-09-24, DEF-CUS-6537) removed; red since then, not this lane's. Front-end
  neighbours (FieldVisitOrders, StepUnit, CR-168 preselection): all pass. `tsc` clean. Gates: G78, G31, G15 PASS; G13
  and G32 FAIL with the same findings on the pre-change base (not this lane's).
* **M6 re-run** through `cr171_e2e_matrix_run.mjs` (MVI-E2E-3's runner, unchanged) on a fresh world:
  **153 PASS · 1 FAIL** (was 125 · 3). WO-0053 *Opening read* of electric on E-M6 and WO-0054 *Reconnect visit* of gas
  on G-M6, both raised, windowed and assigned; *Move-in completed* lists *Work orders WO-0053, WO-0054* and prints no raw
  code. The one FAIL is `DEF-BIL-9793` (sewer on the first bill). Photographs at 1440 in
  `08-qa/movein-2026-10-06/def-wrk-9784/` — `M6/` (the runner's 24, `M6-5-completed.png` the done screen) and
  `field-visit-list-E-M3.png` (`10-scripts/def_wrk_9784_field_visit_photo.mjs`: the list for electric meter E-M3 offers
  one *Opening read*). The photographs' footer reads **v2.549.10**: that number was taken by a sibling at push and the
  build was renumbered 2.549.13 with no code change.

**Filed on the way:** `DEF-WRK-9814` — the open *Work order* list is drawn inside the table's box, so on a one-row
table only its first entry shows. Open.

## 30 · Lane DEF-RAT-9791 record (maintenance, 2026-10-06) — version **2.549.14**, then the base-charge rulings

**Part 1 — other utilities' charge codes on one utility's plan screens (`DEF-RAT-9791`, `DEF-TEN-9794`).** Reproduced on PostgreSQL 16: under a role that bypasses row security, Ottumwa-shaped data (two utilities each holding `BASE-SOL` and `AFTER-HRS`) made the plan's Solar section read *Several base codes* and the Charges list carry `AFTER-HRS` twice. Located in `apps/rating/plan_reads.py` (38 reads with no tenant filter), and the same gap in `selectors.py` (16) and `discount_reads.py` (4); all now name the tenant. Guard: `G143` (read modules must name the tenant; prints what it skipped; 21 non-rating chains held on a shrink-only ratchet, listed in `10-scripts/gates/g143_tenantless_reads_baseline.txt`). Hardening asked by the coordinator after the investigator's finding: a production boot ignores both RLS escape hatches and refuses tenant tables missing ENABLE, FORCE or their policy, naming them. Pushed in `004bd21ce` (2.549.14). `DEF-RAT-9791` is **partially-fixed**: the code half is done; which of the two production causes applies (a bypassing role, or a live table missing its policy) is for the investigator to confirm on the live database. Rollback: redeploy 2.549.13 — but if a production boot refuses, fix the database instead, because rolling back restores the leak.


## 31 · Lane BIL-9793 record (maintenance, 2026-10-06) — version **2.549.15**

**`DEF-BIL-9793` (high, money) fixed in `a9748ed89`.** M6's first bill charged sewer to Foundry Works Fabrication Inc.,
whose address (5 Foundry Way, Bay 3) offers electric, gas, water and solar and no sewer.

**Cause.** Not a missing agreement check. Sewer has no service point and so no agreement; the PO's 2026-09-30 option B
bills it whenever water is billed (`gather._unconnected_plan_services`, `_plan_services_not_taken`). Every other service
is bounded by the ADDRESS through its service point (a meter for a service the premises does not offer is refused,
`BR-MET-119`); sewer, having no point, was bounded by nothing. **The bill run and the one-time bill share the code**
(`gather.gather_account`), so a bill run would have overcharged the same way — any account at an address whose service
list leaves sewer out, on a plan that prices sewer, while it takes water.

**Fix (one source).** `_unconnected_plan_services` takes the anchor premises' `services_available`
(`_services_the_address_offers`): a `%`-of-service whose address list is recorded and leaves it out is *not in
service* — no line, named on the clerk's review list. A list never recorded (`NULL`) narrows nothing. Judgment recorded
in the decision log (*"SEWER FOLLOWS WATER ONLY AT AN ADDRESS THAT OFFERS SEWER"*); review-ledger row PENDING, in plain
words: *"Foundry Works never started sewer, so its first bill no longer carries $38.25 sewer usage and $9.00 sewer base,
and its tax falls by the tax on $47.25."*

**Proof.** `tests/test_def_bil_9793_sewer_needs_the_address_to_offer_it.py` (4 cases through `runs.price_account`) — tc1
and tc4 red on the tip on PostgreSQL 16 (`assert ['sewer'] == []`), green after. With it, `tests/golden`,
`test_br_bil_300_services_rulings_2026_09_30.py` and `test_br_bil_301_not_connected_zero_line.py`: **56 passed, 1
xfailed** on PostgreSQL 16 (`config.settings.pgtest`); golden files untouched.

**M6 re-run end to end on 2.549.15** (fresh world `sbh_b9793w`, runserver + `server.mjs`, clerk Jo Ramirez, 1440):
**154 PASS · 0 FAIL** (§28.1 read 125 · 3; `DEF-WRK-9784` and `DEF-CUS-9785` were fixed by their lanes in between). First
bill: electric $127.50 + $630.00, gas $97.75 + $10.56, solar $112.00 + $0.00, water $44.20 + $63.75, CONN $25.00, no
sewer; State 6.25% **$67.86** and County 2.00% **$21.72** on **$1,085.76** — **$1,200.34** (was $1,251.48; −$47.25
sewer, −$3.89 tax). The readback's `DEF-BIL-9793` label is removed. **M7 regression (sewer offered) on the same world:
100 PASS · 4 FAIL**, the same four known defects as §28.2, sewer still $81.00 + $9.00. Output and photographs:
`08-qa/movein-2026-10-05/e2e/M6-2.549.15/`, `M7-2.549.15/`.

**Already-issued bills.** Searched every lane world database on the shared PostgreSQL 16 cluster (13 databases): 200
issued or corrected sewer lines, **none** at an address whose list leaves sewer out. No issued bill needs a credit; none
was created. The shared development database at port 5432 could not be read from this lane (peer authentication), so it
is not covered.

## 32 · Lane CHARGE-CODE-FIVE record (maintenance, 2026-10-06) — version **2.550.0**

Not move-in work; recorded here because this branch's lanes report into this file. Plans & Rates › Charge codes,
eight fixes the PO asked for (five in the first brief, three — *"fix this"* — added mid-lane). Decision log rows
*"AN "ENTERED WHEN USED" CHARGE CODE MAY CARRY AN OPTIONAL DEFAULT PRICE"* (the PO's ruling, recorded before any
code) and *"CHARGE CODES — EIGHT PO-REQUESTED FIXES"* (our judgments). `BR-RAT-1054` AMENDED 2026-10-06.

| # | Defect | What was wrong | What changed |
|---|---|---|---|
| 1 | `DEF-RAT-9803` | Kind chips (*All · 37 · Base · 9 …*) beside the search box | Kind is a `+ Filter` dimension with counts (opt-in `counts` on `TableFilterConfig`), applied as *Kind: Base ×*; `f.kind` unchanged; `KindChips` and `withKind` deleted |
| 2 | `DEF-RAT-9804` | Locked values drawn dimmed (45%) or as a plain text box | Opt-in `locked` on `SelectField` / `SearchSelectField` (`FormModal.tsx`, `LockedBox`): full-strength text, read-only box, no chevron; every fixed value on the wizard uses it |
| 3 | `DEF-RAT-9805` | *Apply automatically: Yes* saved on a one-time code and did nothing | Confirmed first: only the bill run's fee reader (omits) and R4 (refuses) read the flag, both only beside `recurring`. Server refuses by field (`rating.charges.auto_apply_one_time`); the form shows No, locked, *"One-time fees are never automatic."*. `OQ-RAT-12464` narrowed (one-time half) |
| 4 | `DEF-RAT-9806` | Edit's Code a text box | Add's searchable dropdown, `locked` |
| 5 | `DEF-RAT-9807` | No default price for *Entered when used* | 🔒 A `per_case` code may carry ONE optional *All sizes* amount (Pricing step, blank allowed); served as `default_amount` by `charge_by_code` and the move-in quote, never as `amount`; the bill run's fee reader and the portal's fee quote ignore it. The One-time bill, the move-in's *+ Add fee* and New connection *Add fee* start the clerk's box at it (`moneyMath.startingAmount`, never rounds). Reprice of a code in use needs a reason (`BR-RAT-1016`, unchanged mechanism) |
| 8 | `DEF-RAT-9811` | Nothing said an Other charge cannot be a late fee | Help under *What is it?* on Add: *"Fees a clerk adds. Late fees: choose Plan charge."* |
| 9 | `DEF-RAT-9812` | Percent pricing only under Penalty, unsaid | Help under *Type*: *"Late fees: choose Penalty."* |
| 10 | `DEF-RAT-9813` | Recurring + automatic saved silently | Kit `WarningBox`: *"Bills every account, every bill."* — a warning, never a refusal; not on base codes |

**The PO-review statement (review ledger row PENDING), verbatim:** *"App-Fee is Entered when used with a default of
$10.00. When a clerk adds it, the amount starts at $10.00 and they may type $25.00; the bill shows the amount they
ended with. With no default, the clerk types it every time, as today."*

* **Not changed, deliberately:** Rate schedules' Service chips and the Runbooks library (not asked); service-request
  fees still refuse an *Entered when used* code (that door takes no clerk amount today — a new capability, not this
  ruling); a move-in PLAN row priced *Entered when used* still cannot be typed into (the Fees table types only
  added rows) — both noted, not filed as defects of this lane; R4 still refuses a `per_case` code on a periodic bill.
  No migration; TAP, IMPACT, DAMAGE and BULK-WATER keep no default. `plan_reads.py` and the base-code overlap guard
  were not touched.
* **Red first.** Backend `tests/test_def_rat_9805_9807_charge_code_rulings.py` (12 cases) on a worktree of the pre-fix
  tip `580a99f8d`: **9 failed, 3 passed** (`VAL-002 (rating.charges.per_case_states_no_price)` ×6,
  `KeyError: 'default_amount'`, `DID NOT RAISE ValidationError` ×2; the 3 that pass are guards that must hold before
  and after). Front end `chargeCodeEightFixes.dom.test.tsx` (7 cases) on the pre-fix tip: **6 failed** (e.g.
  `expected <div …> to be null` — the chip row; `cc-kind: expected false to be true` — not locked; `expected 'Fees a
  clerk adds.' to contain 'Late fees: choose Plan charge.'`; `expected null to be '10.00'`).
* **Green.** SQLite: the new file 12 passed; with 17 neighbouring charge-code, auto-apply, one-time-bill and move-in-fee files, **244 passed, 5 skipped** (PostgreSQL-only cases). **PostgreSQL 16** (`config.settings.pgtest`): the new file +
  `test_def_rat_8753_class_terms_and_per_case.py` + `tests/golden` — **48 passed, 1 xfailed** (golden's own declared
  xfail), golden unchanged. `test_def_rat_8753`'s per-case case was amended for the superseded clause (a posted
  default is accepted; a size table beside `per_case` still refused). vitest: `features/rating` + FilterBar +
  FormModal 61 files (970 passed; 12 timed out at 5 s under load and passed, all 14 files, with a 30 s timeout —
  201 passed); one-time bill, move-in wizard, build record, `src/styles` (Route B), WarningBox 27 files, 331 passed.
  `tsc --noEmit` clean on the local install after a planted error went red. Gates: G7, G15, G31 PASS; G13, G32, G33
  red only on keys and props this lane did not touch (G33's `rating.schedules.*` from `63278ffc7`, 2026-10-05; G13's
  `uomsPending` from `7fb6de07e`, 2026-10-02; G32's 21 from earlier lanes) — my two refusal keys are in neither list.
* **Browser, 1440**, `10-scripts/def_rat_9803_charge_code_eight_fixes_walkthrough.mjs` on the lane's PostgreSQL 16
  world (the M-matrix dump, APP-FEE added through `create_charge` with a $10.00 default): **17 PASS, 0 FAIL**,
  photographs in `08-qa/charge-codes-2026-10-06/2.550.0/` — `1a-list-toolbar`, `1b-filter-dropdown`,
  `1c-kind-base-chip`, `2-edit-app-fee-step1-locked` (computed colour `rgb(32, 30, 29)`, opacity 1 on all four),
  `2b-edit-re-read-step1-locked`, `5a-pricing-default-10`, `5b-one-time-bill-starts-at-default`,
  `5c-one-time-bill-clerk-override-25`, `8-other-late-fee-hint`, `9-type-late-fee-hint`, `10-bills-everyone-warning`,
  `3-one-time-auto-locked-no`.
* **Rollback.** Redeploy `2.549.10`; no migration. A default saved under 2.550.0 stays as an *All sizes* row, which
  2.549.10 ignores at every clerk door and closes on the code's next save.

## 33 · Lane DEF-RAT-9792/9780/9781 record (maintenance, 2026-10-06) — versions **2.549.11**, **2.549.12**, **2.550.1**

Decision log *"THE MANUAL DISCOUNT DOOR REFUSES AN AUTOMATIC DISCOUNT, AND MOVE-IN EVIDENCE BECOMES THE
ENROLMENT'S PROOF"* holds the judgments.

### 33.1 · `DEF-RAT-9792` — no hand enrolment in an automatic discount (`2.549.11`, `436be22a5`)

* **What was wrong.** Plans & Rates' *+ Enroll an account* (and `POST /accounts/{id}/discounts` behind it)
  enrolled an account in Municipal account, Paperless or Autopay; the nightly sync ended it the next night.
  §25's fix covered the move-in only.
* **What changed.** `customers.discounts.claim_assistance` — the door every person uses — refuses a
  discount whose version in force today is automatic, read through rating's
  `automatic_discount_ids` (§25's reader, not re-derived), key `customers.moveIn.discountAutomatic`, field
  `programme_id`, 422. `GET /discounts/{id}` serves `enrolled_automatically`; `DiscountAccountsTab` draws no
  *+ Enroll an account* when it is true. The nightly sync and the sample data call `enrol_account` directly
  and are unchanged. `test_br_rat_076`'s CAPAUTO re-pointed to *apply and approve, no proof* with its
  assertions intact (its subject is the no-proof programme, not the mode).

### 33.2 · `DEF-CUS-9780` — the move-in's evidence on the enrolment (`2.549.12`, `9160c9572`; `2.550.1`, `90dedd1d7`)

* **What was wrong.** `cap-award-letter.pdf` uploaded at move-in sat only in the account's KYC folder; CAP
  read *Proof pending* with no proof on it.
* **What changed.** `move_in_documents.evidence_cards` names the account's *Assistance evidence* filing
  cards (wizard uploads and request papers) after `write_at_complete`; `move_in_preferences._claims` hands
  them to rating's new `discount_services.attach_enrolment_proof` for every claim that lands *pending* —
  one `discount_enrolment_documents` row each, reference = the account document id, kind by
  `proof_kind_for_assistance_evidence`, `restricted` derived. Nothing is verified. `GET
  /discounts/{id}/accounts` serves `proof_document_id` to a System Admin only; the tab draws *View proof*
  (👁, `rating.discountDetail.accounts.viewProof`, eleven catalogues) on a *Proof pending* row that has
  one, and (2.550.1) moves *End* behind `…` there so the row keeps two icons (B14 rule 15).

### 33.3 · `DEF-CUS-9781` — drawn, not built

The Accounts blueprint draws no discount anywhere on the account. Proposal (not built, for the PO):
`08-qa/discounts-account-proposal-2026-10-06/account-discounts-proposal-1440.png` and its HTML — a
*Discounts* group on the Overview tab under *Plan*; columns Discount · State · Value · From · To · Proof;
states *Proof pending* / *Receiving* / *Ended*; the proof eye for a System Admin only; no enrol or verify
on the account. The defect stays **open** until the PO answers the picture.
⚠ **ANSWERED 2026-10-06 — NOT NOW.** PO: *"keep it as it until someone ask - if someone ask we will make
the changees"*. Not built; the row stays `open` as deferred until requested (decision log *"S1–S8
SIGNED"*, §38).

### 33.4 · Proof

* **Red first** (a detached worktree of the pre-fix tip `997ccb0a1`, the new file copied in): **6 of 6
  failed** on SQLite — `DID NOT RAISE ValidationError` (claim of MUNI), `assert 200 == 422` (the door),
  `KeyError: 'enrolled_automatically'`, `assert 0 == 1` (no proof row), `DiscountEnrolmentDocument.DoesNotExist`,
  `KeyError: 'proof_document_id'`. Front end: the two new dom cases failed on the old tab (`found <button>`
  for *+ Enroll an account*; no *View proof* button).
* **Green.** SQLite: the new file + `test_w5_eligibility_and_deposit_carry.py` +
  `test_def_cus_9779_…` + `test_cr171_p225_move_in_documents.py` + `test_cr171_p1_15_…` +
  `test_cr166_discounts_round2.py`: 91 passed, 2 skipped, 1 failed — the failure was the new CAP case
  pricing on a date before its own enrolment (a test bug, fixed to price on the enrolment day), then the
  new file **6 passed**. **PostgreSQL 16** (`config.settings.pgtest`): the new file + `test_def_cus_9779_…`
  + `test_cr171_p1_29_money_pg.py` + `tests/golden`: **39 passed, 1 xfailed** (golden's own declared
  xfail) — golden unchanged. A first PG run was lost to its cluster being shut down mid-run (19
  connection errors, not code). vitest `discountDetail/` 2 files, 45 passed. `tsc --noEmit` clean after
  a planted error went red (exit 2). eslint clean. G7, G15, G31 PASS. G13 (9 unwired) and G37 (16)
  are red with the same counts on `997ccb0a1` before this lane; G32's 21 unresolved name none of these
  keys.
* **Browser at 1440.** Matrix world (lane l9786's dump) on PostgreSQL 16, gunicorn-free `runserver`
  + `server.mjs`. M3 (Harold Whitfield, CAP + `cap-award-letter.pdf`) through the wizard on 2.549.12:
  **113 PASS · 0 FAIL** (`08-qa/discounts-9792-9780-2026-10-06/M3/`); the database then holds one
  `programme_award_letter` proof on Harold's *pending* CAP enrolment, not restricted.
  `10-scripts/def_rat_9792_cus_9780_walkthrough.mjs` on the build numbered **2.549.17** when it was photographed (renumbered **2.550.1** at push because `2.550.0` landed first; the same code for these screens, so the footers read v2.549.17): **8 PASS · 0 FAIL**
  (`walk/run-2.549.17.txt`) — Autopay has no *+ Enroll an account* (`1-…png`); CAP keeps it and
  Harold's row shows 👁 ✓ … (`2-…png`); a POST of Autopay answers 422 by name; the eye opens the
  account document's content route and the letter is served (200, `application/pdf`; `3-…png` is
  headless Chromium's empty PDF frame); Jo Ramirez (Billing Clerk) sees the row and no eye (`4-…png`).
* **Rollback.** `2.550.0` (row icons), `2.549.11` (evidence), `2.549.10` (the door). No migration.

## 34 · Lane DEF-CUS-9789/9790 record (maintenance, 2026-10-06) — version **2.549.16**

**What was wrong.** (1) `DEF-CUS-9789`: the wizard records every counter payment as still
processing, and a deposit release or a refund counts only cleared money (§26: a refund must never
pay out money that has not arrived). So cancelling a move-in the same day — M1: Avery paid $175.00
by check 2041, $150.00 deposit + $25.00 connection — closed the account and refunded nothing,
and the cheque stayed in the drawer against a closed account. (2) `DEF-CUS-9790`: *Change move-in
date* moves the account's start and its agreements but never the move record (BR-CUS-152); the
details view and the Move-ins list read the record, so after 10/10/2026 → 10/15/2026 the move-in
still read 10/10/2026.

**What changed.**
* `customers/move_in_cancel.py` (🔒): every `processing` payment of the account is CALLED OFF
  through payments' existing Cancel (`payments.cancel.cancel_payment`, reason `not_taken`, note
  *"Move-in MVI-… cancelled"*) inside the cancel's one transaction, before the release and refund
  (which are unchanged). The preview serves `called_off` (one line per payment) and refuses
  `paymentNotCallable` when payments' own Cancel would refuse any of them — before anything is
  written. Hard rule 4: the existing status move + a −amount reversing row, no new path, the
  allow list does not move. Hard rule 5: nothing posts (a processing payment never posted). Hard
  rule 7: both rows of each call-off audited by payments, the account's cancel row lists them.
* `payments/cancel.py`: a read, `uncleared_payments_for_account`, with `refusal_for`'s answer per
  payment. `cancel_payment` itself is unchanged and is the act a clerk already presses on a
  payment (same roles: System Admin, Billing Clerk).
* `customers/move_record_reads.move_in_date_of` — a committed move-in's date is the account's
  `opened_at` (§9.FLOW); the details view (*Moved in* chip, *Moved in on*) and the Move-ins list
  (row and its sort) read it. A move-out keeps its record's date. The opening-read window keeps
  the record's date on purpose (the day the readings were committed against).
* Modal: *"PY-… · $150.00 called off, not banked."* per payment; no refund line when nothing is
  refunded. Two keys in eleven catalogues (`customers.moveDetail.cancel.calledOff`,
  `customers.moveIn.cancel.paymentNotCallable`), NATIVE-REVIEW-OWED.

**Both cases, side by side (the coordinator's instruction; the signed case must keep passing).**
Cleared — Nilesh, $175.00 by check 1043, cleared: $150.00 deposit released + $25.00 → ONE $175.00
refund to Finance, exactly as the PO signed (ruling (B) 2026-10-05, sign-off 2026-10-06); its two
tests are green on SQLite and PostgreSQL 16. Uncleared — Avery, $175.00 by check 2041, processing:
both payments called off, $0.00 refunded because nothing arrived, the customer keeps their cheque.

**Proof.**
* `tests/test_def_cus_9789_9790_move_in_cancel_and_date.py` — 7 cases (2 on PostgreSQL only).
  **Red first** on the old code: `KeyError: 'called_off'`; `assert '2026-08-01' == '2026-08-03'`
  (details view and list); then green. SQLite with the neighbours (the cancel-refund file, the
  cancel file, the flow-doors file): **35 passed, 5 skipped** (the PostgreSQL cases). PostgreSQL 16
  (this file, the cancel-refund file, the cancel file, `DEF-BIL-9751`'s file and payments' own
  Cancel file): **59 passed, 0 skipped** — the call-off commits with the close, and a refusal
  after the call-off rolls the payments back to processing. `vitest` (the move detail file + the
  i18n suite): **149 passed**; `tsc` exit 0, shown capable of failing on a planted error first.
* Matrix runner on 2.549.16, a fresh world on PostgreSQL 16 restored before every case, clerk Jo
  Ramirez, 1440 (`08-qa/movein-2026-10-06/def-cus-9789/`): **P4.24 135 PASS · 0 FAIL** (was 128 · 4
  in §28) — the modal lists *PY-261010-0086 · $150.00 called off, not banked.* and
  *PY-261010-0087 · $25.00 …* and no refund; after the press the readback finds both originals
  `cancelled`, reversing rows −$150.00 and −$25.00, no journal entry, no refund, no release, every
  journal entry balanced; the account's Payments tab shows the four rows *Canceled*
  (`P24-a1-cancel-modal.png`, `P24-a6-payments.png`). **P4.25 (copy of M2) 124 · 0** and **P4.25
  proration (copy of M1) 116 · 0** (were 121 · 3 and 113 · 3) — chip *Moved in 10/15/2026*, *Moved
  in on 10/15/2026*, the list row *MVI-26-0007 · 10/15/2026*, base charges $48.00 → $40.26
  (`P25-a2-changed.png`, `P25-a2c-list.png`).
* **Runner, minimally changed (lane MVI-E2E-3's cases, reused):** P4.24's two money checks now
  expect the call-off (the uncleared case) and the readback adds three call-off checks; the fixed
  defects' labels are removed. **And one runner fault found:** P4.25 read the Move-ins list at
  `/move-ins`, which is no screen (*"This screen is not built yet"*); the list is the Accounts tab
  `/accounts?tab=move-ins` (`moveShared.MOVE_INS_TAB_PATH`). So §28's list FAIL was the runner's
  address, not (only) the product — corrected.
* **Filed, left:** `DEF-CUS-9815` — the account's Activity log still dates *Opened* by the record
  (`account_activity._moves_leg`), an account-history surface with its own union shape.
* **Rollback.** Redeploy `2.549.15`. No migration. Payments already called off stay cancelled
  (hard rule 4); a clerk re-records a payment if the cancel itself was the mistake.

## 35 · Lane DEF-9786-9788 record (maintenance, 2026-10-06) — version **2.550.2**

**What it fixed — MVI-E2E-3's three M7 findings, and the root of the first.** Worked in its own worktree on
PostgreSQL 16 database `sbh_l9786` (`cr171_e2e_matrix_world.py setup`, dumped once, restored before every run),
backend 8786, front end 5786 (`vite build --mode compose`), 1440. Decision log *"GOVERNMENT · SCHOOLS IS MOVED IN
BY OFFERING GOVERNMENT AGAIN ON SETTINGS"* holds the judgments; law 13, nothing put to the PO.

| Defect | What a person sees now (on 2.550.2) |
|---|---|
| `DEF-CUS-9808` (filed by this lane, before fixing) | Settings › Reference data › Account types: every row has *Stop offering* / *Offer again*; a stopped row reads *Not offered* and keeps every account it has. This is the PO's 2026-09-18 ruling (`OQ-CUS-12407` (a), *"go with option a"*), which reached the register and never the card. |
| `DEF-CUS-9786` | With Government offered again, New move-in › Customer offers *Government* and, under Sub-type, *Schools*. M7 moves in as **Government · Schools** (was Municipal, no sub-type). |
| `DEF-BIL-9787` | A bill drafted for Cedar Ford Independent School District prints **PO number · PO-2026-118** under its mailing address, on the page and in the PDF (BL-2610-000103, a $40.00 fee — the amount unchanged). The first-bill preview carries it too. |
| `DEF-CUS-9788` | The account page's Billing preferences ends with **PO on bills · PO-2026-118**; the move's Account tab shows the same. Shown only when the account has a PO. |

* **Why not move the seed.** Re-parenting the government sub-types under Municipal was the option the PO already
  declined on 2026-09-23 (`OQ-CUS-12618`, *"take it from settings"*, no seed row moved). So the matrix world now does
  what a utility would — Settings › Account types › *Offer again* on Government, through the card's own handler
  (`offer_government`) — and the runner and readback expect Government · Schools.
* **Display only, and issued bills are untouched (hard rule 4).** Stage 6 freezes the PO into the payload at draft
  beside the customer's name, only when the account has one, so every other bill is byte-identical and **only bills
  drafted from 2.550.2 carry it**; a PO changed later never reprints an issued bill (BR-BIL-030). Review-ledger row
  *"A BILL PRINTS THE ACCOUNT'S PO NUMBER"* — NOT YET SHOWN, with the sentence to show.
* **Not editable on the account page.** The Accounts blueprint draws no PO, so it is shown (last in Billing
  preferences, so no drawn row moves) and not made editable; correcting a PO after Complete is a follow-up, not built.
* **Harold's empty sub-type (M3 on 2.549.7) was the runner** (`DEF-MET-9802`, its lane's fix); re-run here green.
* **Red first** on `0b2df5b1b`: backend (PostgreSQL 16) 5 failed / 1 passed — `assert True is False` (legacy
  ignored), `KeyError: 'po_number'` ×3, no refusal for a non-boolean; front end 3 failed (*Not offered* absent; *PO on
  bills* absent ×2). **Green:** 44 passed on PostgreSQL 16 with `test_def_bil_8283_bill_addressee.py`,
  `test_po_20260917_account_types_are_the_tenants.py`, `test_def_4448_every_letter_carries_its_figures.py`; vitest
  226 passed across `moveDetail/`, `SettingsReferenceData`, `AccountDetailPage`, `src/styles`; `tsc` clean (proved able
  to fail with a planted error); eslint clean; G7, G15, G31 PASS.
* **Matrix on 2.550.2:** **M7 104 PASS · 0 FAIL** (Government offered, sub-type Schools, the PO on the first-bill
  preview, the account and the move's Account tab); **M3 113 PASS · 0 FAIL** (sub-type Senior/Low-income). Bill and
  Settings checks: `bill_photo.mjs` PASS, `settings_photo.mjs` 2/2 PASS. Output and photographs:
  `08-qa/movein-2026-10-06/def-cus-9786-9788/` (`M7/M7-2-customer.png`, `M7/M7-w3-account.png`,
  `M7/M7-w10-move-account.png`, `M7/M7-bill-document.png`, `settings-account-types-not-offered.png`).
* **Reds read and dated, not this lane's:** 8 cases in `test_us_cus_schema_and_seed.py` /
  `test_us_cus_003_account_write.py` fail identically on the base `0b2df5b1b` (`AccountType.MultipleObjectsReturned`,
  the platform-era assertions — the file's last change is `d0b2afb50`, 2026-09-17, the day types became the tenant's).
  The gate run (`--changed 0b2df5b1b`) names none of this lane's files among its failures. The first-bill DRAFT on this
  world refuses *"no prior read … minimum"* — that is `DEF-BIL-7972`, already filed.
* **Rollback.** Redeploy `2.550.1`. No migration. Bills drafted on 2.550.2 keep their stamped PO; a type whose flag was
  changed on the card keeps it (ordinary tenant data).

**Part 2 — the PO's base-charge rulings of 2026-10-06 (`DEF-RAT-9797`..`9800`), version 2.550.3.** Built: an every-class and a one-class base code coexist (the overlap guard refuses only a same class or two every-class codes); the clash is a step-1 warning under Customer class that blocks Continue (`GET /charges/base-clash`); *"One per customer class."* in all eleven catalogues; a schedule version that starts billing names its base code — the only code that could serve it is written on it, two or more refuse *"Choose a base charge code."*; live schedules naming none keep billing as today and are listed (`GET /rate-schedules/base-to-choose`, a notice and a per-row *Choose a base code*; 5 of 12 on the walk utility); the plan screen reads *Choose a base code* where it read *Several base codes*. Not built, deliberately: no stored schedule is changed and nothing is chosen for one. Walk at 1440: `08-qa/screens/def-rat-9791-2026-10-06/` (`10-scripts/def_rat_9791_base_codes_walkthrough.mjs`, 8 PASS). Two `DEF-RAT-6932` cases amended in place: an emptied picker with one serving code now names it (the ruling supersedes *"this schedule names nothing"*). Rollback: redeploy 2.550.2; no migration.

## 36 · Lane GRACE-ON-THE-CODE record (PO ruling 11 (a), 2026-10-06) — version **2.551.0**, commit `7abe17ee1`

* **What the PO asked.** *"Whne charge code is late fee system shoud ask garce perios it should based on tthat billing should apply this fee on neect consecutive bill"*, ruled 11 (a): *"Put grace on the late-fee code. When Type is Penalty, the form asks Grace days (default 5) and Calendar / Business days, and billing uses the code's grace. The Settings default stays as the starting value for new codes."* Filed as `DEF-RAT-9816` (the PO's request, not a miss of ours).
* **Built.** `charges.grace_days` / `grace_mode` (`rating/0066`, with CHECKs 0–30 and calendar | business; every existing penalty code seeded with its utility's current grace under `app.tenant_id` — measured on the walk world: *3 penalty code(s) seeded with 5 calendar day(s)*). New/Edit charge code step 1 asks **Grace days** and **Counted in** when Type is Penalty, starting at Billing defaults' grace; Review and View details › How it bills show *5 calendar days*. Billing (`late_fee.assess_late_fee_for_plan`) assesses on the grace the plan's late-fee terms carry (plan override stated before the ruling → code → Billing defaults) and refuses a caller grace that disagrees. A plan's Charges table (details and Edit) shows *Grace: 5 calendar days* under the late fee's *When*, *(this plan)* where an old override applies; the API refuses a new plan override by name.
* **Our judgments** are the decision-log row of the same day (*"THE LATE-FEE GRACE IS BUILT ON THE CHARGE CODE"*). **Plans carrying an override in the sample data: 0** (`seed_demo` writes none; 0 rows on three lane databases).
* **Found on the way, fixed in the same commit:** the plan read's normaliser (`api/planFormEndpoints.chargeSection`) dropped the new `grace` field, so the details page showed nothing while the API served it — hard-won law 2, found by the 1440 walk and now asserted in `chargeCodeGrace.dom.test.tsx`.
* **Proof.** Backend `tests/test_po_20261006_grace_on_late_fee_code.py` 10/10 on PostgreSQL 16, red first (code's grace ignored → 3 failed, *"the tenant's 5-day grace must not reach this fee"*); with the CR-078, DEF-RAT-8827, DEF-RAT-8753, GT-8 grace files and `tests/golden`: **67 passed, 1 xfailed** on PostgreSQL 16 — no golden test changed. Frontend `chargeCodeGrace.dom.test.tsx` 6/6 (red first: fields hidden → 3 failed, *Unable to find a label … Grace days*); `src/features/rating`, `src/api`, `src/i18n` 1157 passed. Walk `10-scripts/grace_on_late_fee_code_walk.mjs` **7 PASS / 0 FAIL** at 1440 on PostgreSQL 16; photographs `08-qa/screens/grace-on-late-fee-code-2026-10-06/01…05`.
* **Reds not caused here, dated.** `src/api/adminOnlyReads.test.ts` names `NewConnectPremiseStep.tsx` (since `ad3bec69d`, 2.463.0); G32's 21 unresolved keys (e.g. `payments.refund.method_unknown`, since `889628807`, 2026-09-24); G13 and G33 list files and keys this lane did not touch.
* **Finance re-sign owed** (❄️ B4/B5 late fee): *"Due 1 Nov, grace 5 days on LATE, $100.00 unpaid after 6 Nov → $5.00 on the next bill; grace 10 days on LATE → no fee until after 11 Nov."* Review-ledger row PENDING.
* **Rollback.** Redeploy `2.550.3` and leave `rating/0066` applied: the two columns go unread and billing's grace returns to Billing defaults, which is what every existing penalty code was seeded with.

## 37 · Lane APP-FEE-AUTO record (PO rulings 2026-10-06, maintenance) — version **2.552.0**

**What the PO asked.** Two rulings the same day, recorded verbatim in the decision log before any code:
*"No - we wil ahve application fees as zero and pprovide option to waive off"* (no "we charge a fee"
setting; a utility without a fee prices it at $0.00 and staff can still waive) and *"Should the
application fee be added to every request automatically? I recommend (a)."* (every new request gets
the fee line automatically). Filed as `DEF-CUS-9819` (the PO's request); it also settles the
configuration half of `DEF-CUS-6102`.

**What was built.** `charges.is_application_fee` (`rating/0067`, one live code per utility, one-time
only, refused by name otherwise) shown on the charge-code form's *How it bills* and details;
`customers.service_request_service.add_application_fee_line` adds that code's line through
`add_fee_line`'s own row writer and catalogue price inside `create_request` and inside
`create_from_portal(application=True)` (only `portal.services._application` passes it); the request
panel reads *Nothing to collect.* and hides *Record what was handed over* when it has lines and owes
$0.00; a $0.00 unpaid line reads *Application fee $0.00.*; the portal availability read serves
`application_fee` and *Check and send* shows it (*Nothing to pay* at $0.00). Our judgments are in
the decision log (law 13): the flag lives on the code, not a Settings pick; only applications get
it; sample data is not marked.

**Proof.** `tests/test_def_cus_9819_application_fee_automatic.py` 6/6 on PostgreSQL 16 (red first:
with the two creation calls removed, 3 failed — `ValueError: not enough values to unpack (expected 1,
got 0)`); neighbouring suites 216 passed, 1 skipped. vitest: the detail page 73/73 (the new
$0.00 case red first with the hide removed), Check and send 46/46, the form model 2/2, rating
charge-code suites green. `tsc --noEmit` clean after a planted error went red. G7, G15, G31 PASS;
G13 (9 unwired, the oldest dated 2026-08-21) and G32 (21 unresolved) / G33 are red on keys and props
none of which this lane touched. Browser at 1440 on PostgreSQL 16 (matrix world copy
`sbh_appfee9819`): `10-scripts/def_cus_9819_application_fee_walkthrough.mjs` **ALL PASS on v2.552.0**
(`08-qa/def-cus-9819-application-fee-2026-10-06/run-2.552.0.txt`): charge-code form and details
(`1-`, `1b-`), Check and send at $10.00 (`2-`), Kyle Mark's request with the $10.00 line (`3-`), a
$0.00 counter request with *Nothing to collect* and the waive still on the line (`4-`), Check and
send at $0.00 (`5-`).

**Open.** 🔒 HUMAN-REVIEW-PENDING — review-ledger row *"2026-10-06 · THE APPLICATION FEE IS ADDED
AUTOMATICALLY"*, NOT YET SHOWN. ⚠ **SHOWN AND SIGNED LATER THE SAME DAY — PO *"(a)"* on the statement
only; see §44.** **Rollback:** `2.551.0`, leaving `rating/0067` applied.

## 38 · Lane SIGNOFF-S1-S8 record (2026-10-06) — no version

**What the PO signed.** *"S1–S8 approve"* — eight plain-English statements with their figures, S8 a ❄️ finance
re-sign (HUMAN-GUIDE §6). Decision log *"S1–S8 SIGNED"* holds all eight verbatim; each has an AMENDMENT row
in `09-human-review-ledger.md` RATIFIED 2026-10-06 on that statement only, the original rows left as written
and every docstring still `HUMAN-REVIEW-PENDING` (G7). `BR-BIL-008` and `BR-RAT-1011`'s note read
**RE-SIGNED 2026-10-06**.

| | Statement | Signed test | Red by breaking |
|---|---|---|---|
| S1 | Foundry Works, no sewer: −$38.25 usage, −$9.00 base, tax on $47.25 | `test_def_bil_9793_…` | `offered=None` in `gather_account` |
| S2 | App-Fee default $10.00, typed $25.00 billed | `test_def_rat_9805_9807_…` | `default_amount: None` |
| S3 | Harold's letter on CAP; $6.00 of $60.00 once verified; Municipal not by hand | `test_def_rat_9792_def_cus_9780_…` | proof attach skipped; automatic refusal skipped |
| S4 | Avery's cheque 2041 called off; Nilesh one $175.00 refund; one refusal refuses all | `test_def_cus_9789_9790_…` | call-off skipped; refusal pre-check dropped |
| S5 | *PO number PO-2026-118* under the mailing address; issued bills untouched | `test_def_cus_9808_bil_9787_…` | PO not stamped |
| S6 | W-ALL $8.00 / W-COM $15.00 by the named code; duplicates refused | `test_def_rat_9797_9800_…::test_s6_…` | one-class code never clashes |
| S7 | one code written, two asked, live un-named listed | `…::test_s7_…` | only code not written; two not asked |
| S8 | grace 5 → $5.00 after 6 Nov; grace 10 → none until after 11 Nov | `test_po_20261006_grace_…` | grace fixed at 5 |

Green: 61 passed, 2 skipped on SQLite; 63 passed on PostgreSQL 16. `git diff` on `06-backend/apps/` empty after
every break was restored.

**S3, one sentence superseded the same day.** *"Nobody can add an account to Autopay, Paperless or Municipal
account by hand"* — the Autopay and Paperless half is reversed by D2 (b) (`8c842a84e`); Municipal stands. The
test asserts Municipal only.

**Found while writing S7's test — `DEF-RAT-9829`, filed, not fixed.** A live water schedule naming no base code
bills a residential account W-ALL $8.00 as before, but a commercial account on it refuses with *"2 base charge
codes for water. Scope them on Charge codes."* once W-COM sits beside W-ALL — so *"keep billing as today"* holds
for one class and not the other.

**`DEF-CUS-9781` (§33.3) — not built, by ruling.** PO: *"keep it as it until someone ask - if someone ask we will
make the changees"*. The row stays `open` (the status tool has no *deferred* value); the decision log carries the
deferral. G7 PASS before and after.

## 39 · Lane D3-D4 record (PO rulings D3 (a) and D4 (a), 2026-10-06) — versions **2.553.0** and **2.554.0**

**D3 — partner systems receive a company under its legal name (`DEF-INT-9796`, `fdf85dfc7`, 2.553.0).** The partner
Customers API (`/partner/v1/accounts`, `/partner/v1/consumer-info`) kept its own copy of the old contact-name rule, so
Grace Fellowship of Cedar Ford went out as *Ruth* / *Okafor*. It now reads the company from the one current-customer
read the account page uses (`customers.selectors.current_customers_for`): `customer_name` and `first_name` = the legal
name, `last_name` null, new `organization_name` = the legal name (null for a person); email and phone stay the contact's.
No contract defined an organisation-name field, so the route's own documentation (and `openapi/schema.json`,
regenerated with `export_openapi`) now describes it; CHANGELOG 2.553.0 carries the *Partner API change* with the
church before/after. Person accounts unchanged. Tests: `test_def_int_9796_partner_company_legal_name.py`, red first
(4 of 5) then green on PostgreSQL 16; the page-statement bound in `test_cr110_…` moved 3 → 4 by exactly the added read.

**D4 — PO on bills is editable in Billing preferences (`DEF-CUS-9820`, `8f7f4f8cc`, 2.554.0).** `po_number` joined
`PATCH /accounts/{id}` (same roles, audited before/after; trimmed; blank clears; over 60 characters refused under the
field). The Billing preferences dialog gained *PO on bills* (existing key, already in all eleven catalogues). No billing
file was touched (the bill stamp file signed today as S5 is unchanged): a bill stamps the PO at assembly. Tests:
`test_def_cus_9820_po_on_bills_editable.py` (5, red first 4 of 5, then green on PostgreSQL 16) and
`AccountPanelEdits.po.dom.test.tsx` (3, red first on the base tree, then green).

**Walked at 1440 on a lane stack (2.554.0, M7 run 104 PASS / 0 FAIL to create the school):** AC-2026-00058,
Cedar Ford Independent School District. Bill BL-2610-000103 issued on 10/06 with PO-2026-118; Billing preferences
changed to PO-2027-044 (audit row before PO-2026-118 / after PO-2027-044); bill BL-2610-000104 raised on 10/13 prints
*PO number PO-2027-044*; BL-2610-000103 still prints PO-2026-118. Photographs: `08-qa/movein-2026-10-05/e2e/D3-D4-2.554.0/`.
The bill SCREEN (`/billing/bills/{id}`) does not show the PO; the printed bill does, which is where A19 rule 4 puts it.

**Reds seen and not caused here, dated:** `test_cr030_w2_customer_no_search.py` — three cases fail on the base tip
`4a75e8831` before any change of this lane (customer number `None`). `test_cr094_n_account_edit_scope.py` tc6/tc6b —
`REFUSED_FIELDS` holds 39 not 36 and fifteen account columns answer *unknown field*; those columns arrived from
2026-09-19 onward (`b08cf8f93`), before this lane.

## 40 · Lane DEF-CWP-9795 record (maintenance, 2026-10-06) — version **2.555.2**

* **What was wrong.** The customer portal's *Your account* (`CWP-065`) read only `accounts.tax_exempt`. Ruling (A)
  (`DEF-CUS-9724`) leaves that flag false for a move-in certificate, so M5's church — certificate against the City of
  Cedar Ford utility tax, to 12/31/2028 — had **no Tax panel at all** on its own portal page. **Reproduced first** in a
  browser on a local stack (`08-qa/screens/def-cwp-9795-2026-10-06/before-certificate-1440.png`, `-390.png`): the walk
  failed 3 of 3 certificate cases with *"(no Tax exempt panel)"*.
* **Located / blast radius.** Mounted file `07-frontend/src/portal/accounts/YourAccount.tsx` (route `/account`), read
  `apps/portal/selectors.account_summary`. Only other portal reader of the flag: none (grep of `tax_exempt` under
  `apps/portal/`). The staff reads (`AccountTaxExemption.tsx`) are untouched.
* **Fix.** `portal/seams/customers_seam.live_tax_exemptions` → `customers.seams.account_tax_exemptions` (the staff
  page's read, rating's `exemption_certificates_for_account`): live rows only, revoked never arrive, expired dropped,
  certificate number not passed on. `account_summary` serves `taxes: [{tax, until}]`; the panel draws one
  *Exempt from / Runs out* pair per certificate (the layout's *From / Runs out*). Blanket exemption unchanged.
  Judgments (no number on screen, the label) are the decision-log row of the same day.
* **Proof.** Backend `tests/test_def_cwp_9795_portal_exemption_certificate.py` 5/5 on PostgreSQL 16, red first (2
  failed); neighbours `test_us_cwp_031_your_account.py` + `test_def_cus_9774_9776_…` 15/15 on PostgreSQL 16.
  `YourAccount.dom.test.tsx` red first (1 failed) then 16/16. `tsc` clean (proved able to fail). Browser walk
  `10-scripts/def_cwp_9795_walk.mjs` on world `10-scripts/def_cwp_9795_seed.py`: 6/6 at 1440, 390 and 320,
  certificate and blanket, no sideways scroll, number never on screen. Photographs: `certificate-1440.png`,
  `certificate-390.png`, `certificate-320.png`, `blanket-*.png`. (The bundle photographed was built before the
  version bump, so its footer reads 2.551.0; the code is this fix.)
* **Accessibility (eight questions).** 1–2: the change adds no control; the panel's one button is unchanged. 3: no
  input. 4: headings unchanged. 5: the new row uses the panel's existing label/value tokens. 6: works at 390 and 320
  (WCAG reflow) — the long tax name wraps; text enlargement NOT measured. 7: nothing happens on this panel. 8: no
  money moves.
* **Reds not caused here, dated.** G13 names `RateScheduleWizard.tsx` `uomsPending`/`correcting` (since `a16e68746`,
  2026-08-21) and `moveReadsCapture.tsx` `readAtLabel` (since `3182e512f`, 2026-08-26).
* **Rollback.** Revert the commits; nothing was written to data.
## 41 · Lane DEF-CWP-9817/9818 record (PO report + PO ruling (b), 2026-10-06) — version **2.555.0**, commit `aa3e68d30`

**What was wrong.** Start service (`CWP-008`) asked the address as ONE free-text *House number and street* box
plus a unit. The Customer Portal blueprint (p31, *15 Start service · 1 Address*, rendered and read as an image)
draws *Street address · Town · ZIP code · Is there a unit or apartment number?*. So the premises match used the
street alone — `31 Palm Ct` in ZIP 78701 was taken for Pine Hill's 78702 property — and steps 2–4 printed what was
typed (the PO's screenshot: *"Haustin Towers 2"*). Separately, the PO ruled (b) that the applicant picks the
customer Category and Sub-category on step 3 (verbatim in the decision log, same day).

**What changed.** Step 1 asks the four drawn boxes (town and ZIP required, ZIP 5 digits or ZIP+4, no state — the
drawing asks none); the check and the draft match street + town + ZIP through `metering.address_match` (the
Approve window's matcher, one exact row only); the parts go to the request's `_as_given` columns (`portal/0015`
holds them on the draft); every later step prints ONE server-composed line in US form — the premises' address when
matched, the typed parts with the utility's state otherwise (`1841 Quarry Hill Ct, Apt 12, Silver Creek, TX
78611`). Step 3 asks Category (required) and Sub-category (optional, filtered by category) from Settings › Account
types' offered rows; Check and send restates both; Send writes them to the request with an audit row; the clerk's
*Customer category* row shows them and the clerk can still change them. The staff *Address as given* row now
prints the town and ZIP given. Rules `BR-CUS-1117`, `BR-CUS-1118`.

**Not built, stated:** *Or use my location* (drawn on p31); offering the nearest matches for an address not
recognised (the blueprint's state); Track is unchanged because it serves no address at all.

⚠ **ONE MISMATCH TO KNOW ABOUT.** The question put to the PO quoted *"Type: Not yet classified"* on Kyle Mark's
request. On the request page that **Type** row (and the head's *NOT YET CLASSIFIED*) is the job classification —
move-in or new connection — which the clerk settles; it is not the customer category. The ruling names *"all seven
categories and their sub-categories"* from Settings, which is the customer category, so that is what was built:
the pick lands in the request's *Customer category* row (photo 07), and *Type* still reads *Not yet classified*
until the clerk classifies the job. Decision log judgment 12.

**Proof.**
* Backend: `tests/test_def_cwp_9817_9818_portal_address_and_category.py` (10 cases) — **9 of 10 red at the tip
  before the change** (the wrong-ZIP case: `assert True is False`, the old matcher matched), all green after; on
  **PostgreSQL 16** (`--ds=config.settings.pgtest`) with the portal, Check-and-send, about-you, start-service,
  custom-fields, documents, request-to-active and the application-fee lane's suites: **114 passed**. The existing
  portal tests that send an application gained a category in their draft (the category is now required).
* Front end: `tsc --noEmit` clean (a planted error went red first); vitest `src/portal` +
  `ServiceRequestDetailPage.test.tsx`: **1,258 passed** after rebase; new cases in `StartService.test.tsx`,
  `StartService.dom.test.tsx`, `CheckAndSend.dom.test.tsx` (US line on rail and Check and send, category lists,
  sub-category filtered and cleared) and `ServiceRequestDetailPage.test.tsx` (as given with town and ZIP).
* Browser: `10-scripts/def_cwp_9817_9818_start_service_walkthrough.mjs` on 2.555.0 against a PostgreSQL 16 world
  (`seed_demo` + `load_sample_data --tenant brazosbend`), **40 PASS · 0 FAIL** at 1440 and 390 plus a keyboard-only
  pass (`08-qa/portal-address-category-2026-10-06/`, 14 photographs + `run-2.555.0.txt`). The keyboard pass found
  the unit box had no `autocomplete` purpose; fixed in the closing commit (`address-line2`).
* Accessibility (the eight questions): 1 keyboard — Tab walks street → town → ZIP → unit → Check, Enter checks;
  2 focus is visible; 3 every box has a bound label and an autocomplete purpose, the ZIP error is tied by
  `aria-describedby` in a polite live region; 4 one `h1` per step (unchanged); 5 kit tokens only, no new colour;
  6 at 390 the boxes stack (photos 390-*), nothing scrolls sideways; 7 the ZIP refusal and *Choose a category
  first.* are announced through the field-error live region / the held line; 8 no money moves on these steps.
* Gates: G7, G15, G31, G81, G84, G85 PASS (G85's declared blind spot 11 → 13). G13 (9 unwired), G32 (21 unresolved)
  and G33 (10 refusal copies over six words, none of them this lane's keys — rating schedules, ledger export,
  integrations, metering import, reports, portal documents) are red with the same findings before this lane.

**Rollback.** Redeploy `2.554.2`; leave `portal/0015` applied (four nullable columns, then unread).

## 42 · Lane PLAN-BLOCK record (PO request, 2026-10-06) — version **2.556.0**, commits `560603383`, `58efe5f37`

* **What the PO asked.** *"In this screen all component bind in plan like rate, charge,code, base reate, taxes, discount needs to visible this data is required for clark while attaching the plan based on data clark will take decision"*; on the drawing (claude.ai/artifact/9poRZzcU1ooxCw9A78jXgy) *"We dont want any section on step 2 should be changed - only Services and plan"*; then *"okay - please do these changes"*. Filed as `DEF-CUS-9821` (the PO's request) and the agreed table written to the decision log BEFORE code (*"NEW CONNECT STEP 2: THE 'THIS PLAN' BLOCK IS REDRAWN …"*).
* **Built.** One component, `features/rating/planSections/ThisPlanBlock.tsx` (B14 rule 43), mounted only on New Connect step 2 (move-in's *See full rates* untouched): summary strip · a warning only when true (schedule names no base code + *Choose a base code ↗*; a service the plan does not cover — the old *WON'T COVER* line, now said once; a base price not set) · Base charges and Usage rates open · Other charges, Deposit, Taxes, Discounts, Outside city closed with a one-line summary · every name a new-tab link · the footer *"Figures come from the plan, for Residential accounts at this address."* The drawing's proposal note and *What each part is for* legend are not built. The *"It is not zero"* sentence never appears.
* **Data.** The plan details page's own read, `GET /plans/{id}`, read ONCE as both shapes (`getPlanWithSections`). The owner's class from step 1 goes as `?classes=` and narrows each service's BASE the way the bill picks it (charges, deposits, taxes keep every class row, as drawn). Five additive facts in `plan_reads`: base `named` + `classes`, tax `customer_classes`, deposit `refundable` (every coded deposit is refundable — the plan write refuses any other type), discount `enrolment_mode` + `proof_required`. No price, rule or stored figure moves; review-ledger row PENDING.
* **Kit over drawing (rule 44), stated:** the warning is the kit's `WarningBox` (its 720px measure, not full width); a min reads *1.50% · min $5.00*; block rows read *0 kWh – 500 kWh · $0.0425 per kWh*; the drawing's figures are illustrations (rule 37).
* **Proof.** Backend `tests/test_def_cus_9821_new_connect_plan_block_read.py` 7/7, red first on `4734f90d0` (7 failed: `KeyError: 'named'`, `'customer_classes'`, `'refundable'`, `'enrolment_mode'`, `plan_sections() got an unexpected keyword argument 'classes'`, the API ignoring `?classes=`); with the plan-read neighbours (round 2, 9519, 12786, 9502, grace, wiz-bill, move-in pricing, plan summary, plan fixes, 9516, 9517) **99 passed** on SQLite. Front end: `ThisPlanBlock.dom.test.tsx` 12/12 (eight parts, warning only when true, five closed by default, every link `target=_blank` under the tenant, Taxes expands); step tests red first on the unwired step (*expected … to contain 'data-facts="this-plan-summary"'*), then green; `src/styles src/i18n src/api src/features/customers src/features/rating` **3581 passed, 3 failed** — none this lane's (dated below). `tsc` exit 0, shown capable of failing (it caught two real type errors in this lane's own first draft). G15 PASS (after three words were translated and two glyph-only values composed in code), G31 PASS, G13 names none of this lane's files.
* **Browser.** World `10-scripts/def_cus_9821_plan_block_world.py` on a CR-171 matrix world (PostgreSQL 16, `mvimatrix`): plan MBSP — Solar on the sample solar schedule naming BASE-SOL; Battery's schedule naming no base code while BASE-BAT and BASE-BAT-RES could both serve a Residential account. Walk `10-scripts/def_cus_9821_plan_block_walk.mjs` **28 PASS / 0 FAIL** at 1440 and 390; photographs `08-qa/screens/def-cus-9821-2026-10-06/` (`1440-01-panel-collapsed.png`, `1440-02-panel-taxes-open.png`, `1440-03-beside-drawing-collapsed.png`, `1440-04-beside-drawing-taxes.png`, `390-*`). At 390 the staff frame keeps its sidebar and the panel is ~110px wide (no page scroll, tables scroll inside themselves) — the staff app is laptop-only by PO ruling (2026-09-10), so this is recorded, not filed.
* **Reds read and dated, not this lane's:** `src/api/adminOnlyReads.test.ts` names `NewConnectPremiseStep.tsx`'s `getRegionalSettings` (since `ad3bec69d`, 2026-10-02); `wizardRailCensus.test.ts` names `taxEditModel.ts`'s three step lists (since `b71588e74`, 2026-10-03); `ReturnedPostBanner.dom.test.tsx` cannot find *"Choose what you found."* (files last touched `35f3cf079`, 2026-09-23; this lane touched neither file nor its keys). Gate reds G3, G6, G8, G10–G14, G18–G20, G26–G28, G32, G33, G129 name none of this lane's files.
* **Rollback.** Redeploy `2.555.2`. No migration; the added read keys go unread.

## 43 · Lane NCT-01 record (PO "go ahead start it", 2026-10-06) — versions **2.554.1**, **2.554.2**, **2.555.1**, **2.556.1**, **2.556.2**

**What the PO asked:** seven New Connect fixes from their own table, in the order N1, N3, N4, N5, N6, N7, N2 — *"go
ahead start it"*. Filed as the PO's reports before any code (`DEF-CUS-9822`..`9828`); the go is the decision-log row
*"PO 'GO AHEAD START IT': SEVEN NEW CONNECT FIXES"*. Maintenance work: each reproduced red first in a test, fixed,
proved green, then walked in a browser.

| Item | Defect | What a clerk sees now | Version · commit |
|---|---|---|---|
| N1 | `DEF-CUS-9822` | Sub-category offers the sub-types set up under the chosen category in Settings › Account types (Residential: Multi-family, Senior/Low-income, Single-family); it clears when the category changes; the choice reaches the owner's account | 2.554.1 · `c6a810ad7` |
| N3 | `DEF-CUS-9823` | One *Attach a file* button; no *Add another document* | 2.554.2 · `4c1b56057` |
| N4 | `DEF-CUS-9824` | *Uploaded by* reads the signed-in clerk and today's date for a file attached in the draft | 2.554.2 · `4c1b56057` |
| N5 | `DEF-CUS-9825` | The eye (and the file name) opens the file: a draft file from the browser's own copy, a request's file through the request | 2.554.2 · `4c1b56057` |
| N6 | `DEF-CUS-9826` | *Show* / *Hide* beside SSN and Driver's license, owner and co-applicant; masked by default | 2.555.1 · `aee75333e` |
| N7 | `DEF-CUS-9827` | The co-applicant asks Full name, Email, Phone, Date of birth, SSN, Driver's license — no owner type, category, sub-category or person/company | 2.555.1 · `aee75333e` |
| N2 | `DEF-CUS-9828` | After Approve, New Connect arrives filled: name, email, phone, category, sub-category, date of birth, street, town, ZIP, unit (step 3), where the bill goes, the utility's own answers, language, co-applicant, *Provided on the request · ends 1234* under an empty SSN box, and the request's documents listed as brought in. At Create the owner's account receives those documents by reference | 2.556.1 · `a5f4092ad` |
| — | `DEF-CUS-9831` (found on the walk) | A draft document's type reads *Contract*, not `contract` | 2.556.2 · `3ad92b184` |

* **N3's *expected, not yet brought* row is deliberately not offered on New Connect.** It never was: step 1 refused a
  row with no file before this change (`DEF-CUS-7851`'s note keeps the route on New Request, where a request can hold a
  promise; a draft build cannot). An empty box still answers *Choose a file to attach.*
* **N2 fills only EMPTY fields.** It overwrote the clerk's name, email and phone on every resume until now. A matched
  premises still wins over the applicant's address. SSN and licence are never served or copied — last four only.
* **N2's documents are LINKED, not copied:** `connections.create_owner_account` calls the move-in's own
  `carry_request_documents` (one stored file, a second filing card, audited), so the photo ID Kyle sent is the same
  stored object on the request and on the account.
* **Server changes, minimal:** `metering/connection_reads._request_prefill_rest` (the extra answers) and two lines in
  `create_owner_account` (`account_subtype` on its allow list; the document carry). No migration.
* **Proof.** Front end `newConnectNct01Fixes.dom.test.tsx` 17 cases, each red first on the code that shipped the defect
  (N1 5 red, N3–N5 3 red, N6/N7 4 red, N2 3 red, `DEF-CUS-9831` 1 red); one case in
  `newConnectSteps12Redesign.dom.test.tsx` superseded by N7 (it asserted the co-applicant had the owner's fields).
  New Connect, kit, styles and i18n suites 1,328 + 658 passed; `tsc` clean except
  `ServiceRequestDetailPage.test.tsx` (below), proved able to fail with a planted error. Backend on PostgreSQL 16:
  `test_def_cus_9822_owner_subtype.py` 2/2 (red: *the sub-type was dropped at the commit*),
  `test_def_cus_9828_build_prefill_everything.py` 2/2 (red: `KeyError: 'address_city_as_given'`, *the request's
  photo ID did not reach the owner's account*), with `test_w6_connection_detail.py`, `test_cr164_owner_preferences.py`,
  `test_def_cus_8020_8021_the_create_button.py`, `test_cr171_p225_move_in_documents.py`,
  `test_portal_request_to_active.py`: 69 passed, 1 failed (below). G15 PASS, G31 PASS, G13 FAIL on nine files this
  lane did not touch.
* **Walk at 1440** (`10-scripts/nct01_new_connect_po_fixes_walk.mjs`, PostgreSQL 16 `sbh_nct01`, seed_demo + sample
  data, local SPA proxied to a local API): Kyle Mark applies on the portal for Haustin Towers 2, Apt-12, Austin 78701,
  with a photo ID; the clerk records Maya Mark as co-applicant, Spanish (Mexico) and his SSN, approves it as a new
  connection from the request page, and New Connect opens on the raised build — **32 PASS / 0 FAIL**. Photographs:
  `08-qa/screens/nct01-po-fixes-2026-10-06/` (approve modal; step 1 owner, Gov-ID from the request, Gov-ID revealed,
  short co-applicant, documents with View; step 2 address; step 3 units; `walk-output.txt`).
* **Found, filed, not fixed here:** `DEF-CUS-9830` — the co-applicant typed on New Connect never reaches the server
  (the commit has no co-applicant path); where a New Connect co-applicant should live (the owner account's co-owner, as
  move-in writes it through the protected `co_owner_models.py`) is a decision for the lane that builds it.
* **Reds not caused here, dated:** `tsc` — `ServiceRequestDetailPage.test.tsx` `'total' does not exist in type
  'ServiceRequestFeesTab'` ×3, since `424d5efff` (2.552.0); vitest `ConfirmDialogTier.dom.test.tsx` census counts
  `features/work/PartsPage.tsx`, since `368d908d7` (2.503.0); PostgreSQL
  `test_w6_connection_detail.py::test_w6_detail_a_system_actor_is_named_rather_than_left_blank` updates `audit_log`,
  which PostgreSQL forbids (BR-AUD-002), since `16d9a6d51`; G13's nine unwired props (`RateScheduleWizard.tsx`,
  `moveReadsCapture.tsx`, `AccountUsageTab.tsx`, `CustomerFields.tsx`, …) — none in this lane's files.
* **Rollback.** Redeploy `2.554.0`. No migration. Accounts opened since keep their sub-type and their filed documents.

## 44 · Lane SIGNOFF-9819 record (2026-10-06) — no version

**What the PO signed.** Asked *"Approve the automatic application fee (built, 2.552.0)?"* — (a) approve / (b)
hold — on the statement *"Kyle Mark's portal request arrives with Application fee $10.00 already on it; the clerk
takes it or waives it. A utility that charges nothing prices its fee at $0.00, and its requests read 'nothing to
collect' with no collect button."* PO, verbatim: *"2. Approve the automatic application fee (built, 2.552.0)? (a).
It's exactly your two rulings: no setting, and the fee added automatically."*

**Recorded.** Decision log *"THE AUTOMATIC APPLICATION FEE SIGNED"* (top); a review-ledger AMENDMENT row RATIFIED
2026-10-06 on that statement only, the §37 row left as written and the nine files' docstrings still
`HUMAN-REVIEW-PENDING` (G7). The row lists what the statement did not cover — one marked code per utility, the
unmarked case, the live-price read, a portal report getting no fee, Check and send's figure, `rating/0067`, and the
staff and counter doors (which rest on ruling (a) itself) — and those stay on the agenda.

**Signed test.** `test_def_cus_9819_application_fee_automatic.py::test_the_statement_the_po_signed_on_2026_10_06`:
Kyle Mark's portal application carries one `APP-FEE` line of $10.00; collected → $0.00 owing; waived on a second
request → $0.00 owing; a utility pricing its code $0.00 gets a $0.00 line owing nothing, the two facts the panel reads
to print *Nothing to collect.*, and the waive still accepted. Red by breaking, one line of
`service_request_service.py` at a time: the portal door's call removed; a $0.00 price treated as no fee; the price
not read from the catalogue ($25.00 for $10.00). 7/7 on PostgreSQL 16 and SQLite; `git diff` on `06-backend/apps/`
empty afterwards. G7 PASS before and after.

## 45 · Lane NCT-02 record (PO ruling (a) on the co-applicant, 2026-10-06) — version **2.557.0**, commit `4a7a24732`

**What the PO ruled:** *"Where does a New Connect co-applicant get saved? (a) Save her the way move-in does: a co-owner on
the new account, SSN scrambled so staff see only the last four digits. It's the same record and the same rules you signed
this morning (Riya G). - but make SSN, Email, Phone , DOb optional for co applicant"* — recorded in the decision log before
any code (*"A NEW CONNECT CO-APPLICANT IS SAVED AS A CO-OWNER"*). Maintenance work; each item red first, then green, then
walked in a browser.

| Item | Defect | What a clerk sees now |
|---|---|---|
| Co-applicant saved | `DEF-CUS-9830` | Maria Mark, typed on step 1 with only her name, is a co-owner on Kyle's new account after *Create*; her blank email, phone, date of birth and SSN stay blank. A request's co-applicant (N2) is saved the same way. Only *Full name* carries an asterisk; a badly typed email holds step 1 with *That email address does not look right.* |
| Portal file's uploader | `DEF-CUS-9834` | *Proof of identity · kyle-photo-id.pdf · Kyle Mark (applicant) · 10/06/2026* — on New Connect and on the request page |
| State | `DEF-CUS-9835` | Step 2's State reads *TX* for a portal request (the portal asks none) |
| This plan | `DEF-CUS-9836` | *Taxes 2 · 2.00% total* for a Residential owner on the residential plan; *Discounts 3 · Autopay discount 0.50% · Municipal account 20.00% · Paperless billing $1.00* |
| Account page | `DEF-CUS-9837` | *Co-applicant: Maria Mark · Email — · Phone —* on `AC-2026-00054` |

* **The write is move-in's, not a second one.** `connections.create_owner_account` takes `co_owners` off the owner
  payload, checks it with `customers.move_in_people.pop`, and writes it inside the build's transaction with
  `write_at_complete` (`service_request_id=None`, so the request's papers are not carried twice). 🔒 `co_owner_models.py`
  and `customers/0080` unchanged. Review-ledger row PENDING with the statement to show (below).
* **Statement to show the PO (PENDING):** *"A clerk adds Maria Mark as co-applicant on New Connect. On Create she is saved
  as a co-owner on Kyle's new account, the same record move-in uses; her SSN is stored scrambled and staff see only the
  last four. Only her name is required; email, phone, date of birth and SSN may be left blank."*
* **Move-in already asks only the name** — its co-owner card and its server both require *Full name* alone; move-in is
  not changed here.
* **The *Anything else* in NCT-01's photograph was the walk, not the product**: that walk attached the photo ID with no
  requirement; the real portal sends one and the request files *Proof of identity*. The new walk attaches on the
  requirement. Judgments in the decision log (*"NEW CONNECT FOLLOW-UPS FROM NCT-01's PHOTOGRAPHS"*).
* **Server changes:** `metering/connections.create_owner_account` (the co-applicant), `metering/connection_reads`
  (`utility_state`), `customers/service_request_reads.documents_tab` (`uploaded_by_role`, one query for the tab),
  `customers/service_request_documents.PORTAL_STORE_PROCESS`, `customers/selectors` (`co_owners` on the account read,
  no identifier), `rating/plan_reads._taxes` + `rating/selectors.plan_combined_tax_rate_display(class_codes=)`. No
  migration. Three catalogue keys in eleven languages.
* **Proof.** Backend on PostgreSQL 16: `test_def_cus_9830_new_connect_co_applicant.py` 7 and
  `test_def_cus_9836_this_plan_tax_for_the_class.py` 2 — 7 red on the shipped code, 2 controls green on both; with the
  neighbours 119 passed. Front end: `newConnectNct02Fixes.dom.test.tsx` 14 and two cases in `AccountDetailPage.test.tsx`
  — 9 red on the shipped code; neighbouring New Connect, account, plan-block, documents and request suites 812+ passed
  (one ThisPlanBlock assertion of the code-first summary updated to the names). `tsc` clean, proved able to fail with a
  planted error; G15, G31, G7 PASS; Route B utilities 11/11.
* **Walk at 1440** (`10-scripts/nct02_new_connect_co_applicant_walk.mjs`, PostgreSQL 16 `sbh_nct02`, local SPA proxied
  to a local API) — **ALL PASS**: Kyle Mark applies on the portal with a photo ID on its requirement, the clerk approves
  into a new connection, adds Maria Mark with only her name, reads State, Taxes and Discounts, presses *Create connection
  ✓* (`CON-26-0129`, `AC-2026-00054`) and opens the account. Photographs: `08-qa/screens/nct02-co-applicant-2026-10-06/`.
* **Reds not caused here, dated:** G13's nine unwired props (`RateScheduleWizard.tsx`, `moveReadsCapture.tsx`, …), none
  in this lane's files, as NCT-01 recorded; PostgreSQL
  `test_w6_connection_detail.py::test_w6_detail_a_system_actor_is_named_rather_than_left_blank` updates `audit_log`,
  which PostgreSQL forbids (BR-AUD-002), since `16d9a6d51` (2026-08-25).
* **Rollback.** Redeploy `2.556.2`. No migration. Co-owners written on 2.557.0 stay on their accounts.

## 46 · Lane AUTO-PAPERLESS record (PO rulings D2 (b) and 4, 2026-10-06) — version **2.558.0**, commit `2b404b460`

**What the PO ruled.** D2 (b), verbatim: *"Offer Autopay and Paperless at move-in as drawn … Clark has to add those discounts. clark can add it later also on account"*. Ruling 4, verbatim: *"so when clark make it on or adds it you ahve to set it up so that next billing cycle pick it - t Harold's move-in, the clerk ticks the Paperless discount ($1.00 off), but Harold's Paperless bill setting is left Off."* Read by the coordinator as (b), kept matched. Decision log row *"PO RULINGS — D2 (b) AND RULING 4"* carries both verbatim and the lane's eight judgments.

**What was built (`DEF-RAT-9833`, filed first, closed fixed in `2b404b460`, 2.558.0).**
1. Move-in Billing step: *Claim discounts* offers Autopay and Paperless again (Municipal account still not); each row carries `pairs_with`, picking it switches that preference On, and setting the preference Off removes the row. The server switches the setting On too, inside the move-in's transaction.
2. Account door: `POST /accounts/{id}/discounts` and Plans & Rates' *+ Enroll an account* accept Autopay and Paperless and switch the setting On in the same transaction (audited `account.updated`, reason `discount_added`). Autopay on a cash-only account is refused by name.
3. Setting On on the account edit, the portal's email-bills choice or the move-in enrols at once (`enrolled_on` = today, unchanged rule). Setting Off still ends it that night. The nightly job keeps an Autopay/Paperless enrolment while the setting is On, a pending account included; it still ends one on Off, a closed account or a plan that no longer carries it.
4. Tests of `DEF-CUS-9779` and `DEF-RAT-9792` amended with a dated note, none deleted; the Municipal-account refusals are unchanged.

**Proof.** New `tests/test_def_rat_9833_autopay_paperless_kept_matched.py`: **11 of 12 RED** on the code before the change (the 12th is the unchanged Municipal refusal), **12 of 12 green** after. With the two amended files: **23 passed on SQLite and 23 passed on PostgreSQL 16** (own cluster). Vitest: StepBilling + discount detail **59 passed**; `tsc` clean (proved able to fail). M3 (Harold) re-run through `10-scripts/cr171_e2e_matrix_run.mjs` at 1440: **118 PASS · 0 FAIL**, including *Autopay and Paperless offered*, *no Municipal account* and *picking Paperless switches the preference On (off → on)*. Database read back: Harold's account Paperless On, PAPERLESS enrolment from 10/06/2026, not_required; the tenant's nightly sweep run straight after ended nothing. New `10-scripts/def_rat_9833_walkthrough.mjs`: Municipal draws no *+ Enroll an account*, Autopay does, enrolling Harold lists him and turns his Autopay On — **ALL PASS**. Regression: `def_rat_9792_cus_9780_walkthrough.mjs` (re-pointed at Municipal, dated note) **8/8**. Photographs: `08-qa/movein-2026-10-06-autopay-paperless/` (`M3/M3-3-discounts.png`, `M3/M3-3-preferences-after-paperless.png`, `account-enrol/1…4`, `regression-9792/`).

**Review.** 🔒 discount enrolment — `09-human-review-ledger.md` row **PENDING** with the statement: *"At Harold's move-in the clerk ticks Paperless ($1.00 off); his Paperless bill setting switches On, the discount is in place for his next bill, and the nightly job keeps it. If he later switches back to paper, the discount ends that night. The same happens when a clerk adds Paperless or Autopay on the account. Municipal account stays automatic."* Golden tests unchanged.

**Found, not fixed.** `DEF-RAT-9839` (low) — the Accounts tab's count does not move after *+ Enroll an account* until reload.

**Record repair.** `ae15541d2` first put a duplicate of the base-charge lane's `DEF-RAT-9832` decision row into the log relabelled `DEF-RAT-9833`; the row text had been kept in the shared scratchpad under a generic name the base-charge lane also wrote. Replaced in `0818c55f7`; the base lane's row untouched.

## 47 · Lane NCT-03 record (PO report + PO ruling (a) on extra solar panels, 2026-10-06) — version **2.558.1**, commit `13a66a332`

**What the PO reported:** *"on step 3 unit - in unit and service user added multiple solar pannel on one unit then service
order, completes, occupancy statsu showing dash"*. **What the PO ruled** (question 6, *"one work order or one per panel?"*):
**(a)** — *"We can create 1 work order for all panels ; but … we have to create those many assets and tag them to unit. since
we want to track them and bill them accordingly"*. Recorded in the decision log before any code (*"EXTRA SOLAR PANELS ON ONE
UNIT: ONE WORK ORDER FOR THE SERVICE, ONE ASSET PER PANEL"*); filed as `DEF-CUS-9840`. Maintenance work: reproduced in a test
red first, fixed, green, walked in a browser.

| What a clerk sees now | Where |
|---|---|
| A second and third Solar on Unit 1 are indented SUB-ROWS, *↳ Panel 2 · Solar panel 10 kW*, under the Solar row | step 3 |
| A panel's Work order, Completes and Occupancy show the Solar row's, greyed, with *Same as Solar row* — never a dash; edited on the Solar row only | step 3 |
| The Solar row reads *3 panels · 21 kW*; carts read *3 carts*, fire lines *2 lines* (counted, never summed) | step 3 |
| ✕ on a panel removes that panel; ✕ on the Solar row asks *Remove Solar from 1? Removes 3 panels · 21 kW too.* | step 3 |
| *Units and work › Assets* lists one line per asset Create makes: *PV / solar · Solar panel 10 kW · 1* | step 5 Review |
| Each asset number names its size when a row holds several: *PV-00015 · Solar panel 10 kW · Installed* | the build's Units tab |

* **The server was already right, and that is the finding of item 4.** Create makes one asset per piece
  (`_commit_unit_services` → `create_asset_for_unit`, In stock, on the unit's ONE service point); the unit's service has
  ONE work order; when it is complete and the clerk activates the unit's Solar, `install_build_assets` installs EVERY asset
  on that service point from that date. Proved on PostgreSQL 16 for solar (21 kW), battery (25 kW), trash and fire (3
  each), and red when the install was broken to take only the first asset (`{'active', 'inventory'} != {'active'}`).
  **Nothing installs at the order's completion alone** — installation is the activation that follows it (`CR-162-BRC10`,
  PO 2026-10-02: *"on activation … asset → Installed"*); the walk does both.
* **The kW comes from the data, never typed per size.** `GET /lookups/service_size_classes` now serves `capacity` and
  `capacity_uom` from the ratified ladder the bill sums (`🔒 tenancy/services.py`, a read; review-ledger row PENDING). A
  size with no capacity counts and sums nothing — a partial sum is the wrong number `BR-RAT-090` refuses to bill.
* **The nouns are keyed by the device's own code** (`pv`, `battery`, `container_cart`, `fire_line`), with a generic
  *piece* for any other — 20 catalogue keys in eleven languages, worded in each (es *placa*, es-MX *panel solar*, id-ID
  *panel surya*, fr-FR *batterie de stockage*).
* **Proof.** Front end `newConnectPieces9840.dom.test.tsx` 11 — the seven DOM cases red on the shipped component (no
  nested row, no summary, no confirm), one of them found passing vacuously by that red run and tightened. Customers,
  build record and kit suites 2,518 passed (2 reds below). `tsc` clean, and it failed on this lane's own first draft
  (`Property 'taken' does not exist`). G15, G31, G7 PASS; Route B utilities PASS. Backend on PostgreSQL 16:
  `test_def_cus_9840_one_order_every_piece.py` 5 with neighbours 19 passed.
* **Walk** (`10-scripts/nct03_new_connect_solar_pieces_walk.mjs`, PostgreSQL 16 `sbh_nct03w`, local SPA built with
  `--mode walk` so it calls only the local API): Kyle Mark applies for water and solar; the clerk approves into New
  Connect; Unit 1 takes three panels; Review lists three; Create (`CON-26-0135`); the Units tab lists `PV-00018`, `PV-00019`, `PV-00020` In stock;
  the technician (`d.ortiz`, field app) closes the ONE solar order (`WO-0062`), the office accepts it, Unit 1's Solar is activated:
  **all three Installed, dated 10/06/2026** — **27 PASS / 0 FAIL at 1440, ALL PASS at 1280**. Photographs:
  `08-qa/screens/nct03-solar-pieces-2026-10-06/`.
* **Seen, not changed:** at 1280 the units table squeezes its Service, Kind and Work order boxes (*Sola*, *Co*, *Sol*)
  because the Asset and Size boxes are sized to their longest option (`DEF-CUS-9093`); the sub-row's name wraps there.
  Nothing is unreachable. The plan the walk used does not price solar (*Solar: not in this plan.*), so the walk proves the
  installed assets and the 21 kW the bill reads, not a priced line.
* **Reds not caused here, dated:** vitest `wizardRailCensus.test.ts` names the tax edit wizard's three step lists, since
  `b71588e74` (2.476.0, 2026-10-03); vitest `ReturnedPostBanner.dom.test.tsx` *"Choose what you found."* not found, last
  touched `35f3cf079` (2026-09-23) — neither file nor its keys touched here; G13's nine unwired props
  (`RateScheduleWizard.tsx`, `moveReadsCapture.tsx` since `3182e512f`, …), as NCT-01 and NCT-02 recorded.
* **Rollback.** Redeploy `2.558.0`. No migration; nothing written differs.

## 48 · Lane DEF-RAT-9832 record (PO ruling on base charges, 2026-10-06) — version **2.558.2**

**What the PO ruled, verbatim** (decision log, top row of 2026-10-06, *"A RATE SCHEDULE THAT NAMES NO BASE CODE BILLS A `$0.00` BASE"*): *"You will take the code from plan -> rate schedule -> base charges - in that case if it is provided then you will take it if it is not provided then you will take it zeo ; but you cannot take W-COM because it is availabel in charge coede - I have provided this before also- you have asked again"*. It restates 2026-09-30. We asked it again, which breaks law 13; that breach is ours.

**What was wrong.** A rate schedule that named no base code still got a base from the charge-code list, picked by the account's customer class. A residential account billed W-ALL's $8.00. A commercial account was refused (*"2 base charge codes for water"*, `DEF-RAT-9829`).

**What changed.** The base is now the code the schedule names, at its price. If the schedule names none, the base is $0.00 and the bill carries the existing warning *"No base charge for Water. Billed $0.00."*. This holds on the bill run, the first bill, the one-time bill, the R1–R7 chain, the base seam used by rate-change impact and the portal, the plan screens (New Connect's *This plan* block reads *Not chosen · $0.00* with *Choose a base code*), the plan list's base total, and the rate schedule's Rates tab and list. The rule for a named code with no price for a size or class is unchanged. S6 (W-COM named → $15.00) still passes. S7's *"keep billing as today"* clause is superseded, and its test is amended rather than deleted.

**What live utilities will see.** Measured on PostgreSQL 16 on the seeded demo utility: all 8 of its 8 live schedules name no base code. Of the 71 accounts on plans, 50 lose a priced base, about $3,307.75 a month. The other 21, which used to refuse for an unrecorded meter size, now bill $0.00. CHANGELOG 2.558.2 carries this under *Deploy note*. `DEF-RAT-9842` files the sample seeders, which need per-class schedules or plans.

**Proof.** `tests/test_def_rat_9832_unnamed_schedule_bills_zero_base.py` has 8 cases. It was RED on the untouched tip (residential `8.0000`, commercial `GatherProblem: 2 base charge codes for water`) and is GREEN after, on SQLite and on PostgreSQL 16. The golden tests are unchanged and green on PostgreSQL 16; GT-6 is still the xfail it already was. Vitest: `ThisPlanBlock.notNamed.dom.test.tsx` went RED with the fix taken out, and 115 of 115 pass across planSections and planForm. tsc is clean. Browser photos at 1440 and 1280 are in `08-qa/screens/def-rat-9832-2026-10-06/`: the plan shows *Monthly base charges $0.00*, the Services tab shows *Choose a base code* with *Base charges $0.00*, and Rate schedules shows *Base code needed on 8 schedules.*

**Left open.** `DEF-RAT-9842`: the seeders. `DEF-RAT-9841`: the one-off `migrate_base_to_charge_codes` still measures the pool; three of its tests are strict-xfail and name it.

## 49 · Lane RAT-9842 record (`DEF-RAT-9842` + `DEF-RAT-9841`, after the PO's base-charge ruling, 2026-10-06) — version **2.558.3**

**What was wrong.** After 2.558.2 a rate schedule that names no base code bills a $0.00 base (PO ruling, decision log *"A RATE SCHEDULE THAT NAMES NO BASE CODE BILLS A $0.00 BASE"*). Our own sample and demo seeders created every schedule naming none, so every newly set-up sample utility billed a $0.00 base. Measured on PostgreSQL 16 on a fresh Brazos Bend (demo seed + Load sample data): 0 of 8 schedules named a code, and the sample load's 100 invoices came to $42,503.95 with every base line $0.00. Separately, the one-off base migration report still told a person to *create* a code where one already existed, and three of its tests were marked expected-to-fail.

**What changed.** Each seeded schedule now names the code its plan's customers pay: water residential `BASE-W`, commercial `BASE-W-COM`; sewer `BASE-S`; trash `BASE-T`; each capacity service its one code; the demo seed's four schedules `BASE-E`, `BASE-W`, `BASE-W-COM`, `BASE-E-IND`; the portal's the code covering a residential account. Electric was the one schedule two plans shared while paying different bases ($12.00 / $48.00), so it is now two: *Sample — Electric usage* (residential, unchanged name) and *Sample — Commercial electric usage* (same tiers). No existing schedule is touched. The migration report's held-row line now reads *"would RAISE the bill from 0.00 to 8.00 if BASE-W were named on its rate schedule"* where a code already charges the figure; it still writes no schedule. Judgments in the decision log, top row of 2026-10-06 (*"THE SAMPLE UTILITY NAMES A BASE CODE ON EVERY RATE SCHEDULE…"*).

**Before and after, per account (fresh Brazos Bend, PostgreSQL 16).**

| Service · class · plan | Accounts | Before the ruling (2.558.1) | 2.558.2, old seeders | 2.558.3 |
|---|---|---|---|---|
| Water · residential · SCW-RES | 60 | $8.00 | $0.00 + warning | $8.00 |
| Electric · residential · SCW-RES | 60 | $12.00 | $0.00 + warning | $12.00 |
| Water · commercial · SCW-COM | 2 | $15.00 | $0.00 + warning | $15.00 |
| Electric · commercial · SCW-COM | 2 | $120.00 / $96.00 (by size) | $0.00 + warning | $120.00 / $96.00 |
| Electric · industrial · SCW-IND | 1 | $180.00 | $0.00 + warning | $180.00 |
| Water · industrial / municipal | 1 / 1 | $0.00 + warning | $0.00 + warning | $0.00 + warning |
| Electric · municipal · SCW-RES | 1 | $0.00 + warning | $0.00 + warning | $0.00 + warning |
| Water · commercial · SCW-RES (register demo) | 7 | $15.00 (by class) | $0.00 + warning | $0.00 + warning |
| Electric · commercial · SCW-RES (register demo) | 7 | refused (size not recorded) | $0.00 + warning | $0.00 + warning |
| **Sample load's 100 invoices** | | **$45,343.83** | **$42,503.95** | **$45,343.83**, every base line identical |

The seven register-demo suites are commercial businesses the CR-030 estate puts on the residential plan; they appear on no bill (0 invoices). Restoring their $15.00 would need the class lookup the PO ruled out, so they are left (decision log (3)).

**Proof.** `tests/test_def_rat_9842_sample_schedules_name_base.py` provisions a sample utility and asserts every live schedule names its class's code; it was RED on the pre-fix tree (*"live sample schedules that name no base code … ['Sample — Commercial water (flat)', 'Sample — Electric usage', 'Sample — Industrial electric usage', 'Sample — Residential water (inclining tiers)']"*) and is GREEN on SQLite and PostgreSQL 16. `test_br_rat_088_base_migration.py` tc6b / tc9c / tc12 are no longer expected-to-fail and pass on both. Golden tests unchanged and green on PostgreSQL 16 (GT-6 the xfail it already was).

**Left open / not mine.** `tc10` in the migration file fails exactly as `DEF-RAT-7141` (filed 2026-09-27) says. `test_us_ten_019_sample_records.py`'s two reads-count tests fail identically on `ed5f506f8`, before this lane.

## 50 · Lane SIGNOFF-S9-S13 record (2026-10-06) — no version

**What the PO signed.** *"S9–S13 approve"* — five plain-English statements with their figures, put to the PO as
a sign-off that confirms in plain words that a built change to a money or customer-record part does what they
want. Decision log *"S9–S13 SIGNED"* holds all five verbatim; each has an AMENDMENT row in
`09-human-review-ledger.md` RATIFIED 2026-10-06 on that statement only, the original rows left as written and
every docstring still `HUMAN-REVIEW-PENDING` (G7).

| | Statement | Signed test | Red by breaking |
|---|---|---|---|
| S9 | Maria Mark saved as a co-owner on Kyle's account; SSN scrambled, last four only; only her name required | `test_def_cus_9830_…` (two runs) | co-owner write skipped; full number in the audit; column stored in the clear |
| S10 | Harold's Paperless $1.00 at move-in, kept tonight, ends the night he goes back to paper; same for a clerk's Paperless or Autopay on the account; Municipal automatic | `test_def_rat_9833_…` | sync never ends; setting not switched On; Municipal addable by hand |
| S11 | size list serves 1 kW / 10 kW; 1 + 10 + 10 = 21 kW, the bill's own sum; no price, no write | `test_def_cus_9840_…` | capacity off by one; a price key added |
| S12 | schedule naming none → $0.00 + warning, residential and commercial; naming W-COM → $15.00 | `test_def_rat_9832_…` | class pool put back; *not set* route removed |
| S13 | every sample schedule names its code; each sample account's code is the one the old class pool picked; an existing schedule is never touched | `test_def_rat_9842_…` | commercial water names `BASE-W` |

Green on PostgreSQL 16 (all five) and SQLite (S9–S12). `git diff` on `06-backend/apps/` and `core/` empty after
every break was restored.

**Narrower than the PENDING rows, twice.** S11 was shown the size list, not the bill (*"21 kW × $14.00 =
$294.00"* stays pending). S13 was shown the sample seeders, not the row's one 🔒 file, the migration report's
held-row sentence, which stays pending in full.

**S13's `$45,343.83` is not in a test.** It was measured once on a fresh demo by no recorded procedure; three
loads on this checkout gave 100 bills of `$60,315.82`, `$47,237.11` and `$51,420.56` depending on how the demo is
loaded. The test asserts the per-account equality that makes the total the same before and after.


## 51 · Lane GIS-SEARCH record (PO GIS review gaps 1, 7, 8, PO "go", 2026-10-07) — version **2.558.4**

**What was wrong.** The inline address search spoke a geocoder's language (`q=`, `limit=`, `key=`) to an ArcGIS
FeatureServer, which ignores all three; it asked for no coordinate frame; and it dropped the City's `Unit`.

**What the code now sends for *2670 Sequoia*** (Ann Arbor's layer, no key held):

    https://a2mapseg.a2gov.org/a2arcgis/rest/services/SEU/SEUQualifiedAddress/FeatureServer/0/query
      ?where=UPPER(Street) LIKE UPPER('%2670 Sequoia%')&outFields=*&outSR=4326
      &returnGeometry=true&f=json&resultRecordCount=9

(URL-encoded on the wire; `&token=<key>` is added when a key is held.) One builder serves the search and the nightly
walk (`gis_layer.query_url`); the `where` is `gis_search.where_clause`, which had no caller until now.

| Gap | Defect | Fix | Proof |
|---|---|---|---|
| 1 | `DEF-INT-9843` | `where=UPPER(<mapped street>) LIKE UPPER('%typed%')`, `outFields=*`, `resultRecordCount=9`, `token=` | URL asserted parameter by parameter; a FeatureServer recording that ASSERTS the request answers *2670 Sequoia Pkwy* |
| 7 | `DEF-INT-9844` | `outSR=4326` always; an answer in any other `wkid` is refused whole, logged, `integrations.gis.foreign_frame` on screen (eleven catalogues), Create refuses too | a `wkid` 2253 recording refuses by name; screen draws *"The city sent unusable map coordinates."* instead of *no matches* |
| 8 | `DEF-INT-9845` | `Unit` (via `field_mapping`) on the candidate and on the wire; the grouping bridge reads the unit's own point | `[None, "A"]` arrives for the building and its unit |

**Red first:** 18 of the 20 new backend tests failed against the pre-fix code (the two that passed assert things
that were already true: no token for an open layer, the nightly walk's URL unchanged); the new screen test failed
against the pre-fix panel. **Green:** 20/20 new, 398 + 8 re-run across the sixteen GIS/integration suites, 35/35
`FindTheAddress.dom.test.tsx`, `tsc` clean, G15/G31/G77 pass.

**Not done here, deliberately.** Grouping the list by building (the field is now there; the screen reads a flat
list). The Ann Arbor recording is CONSTRUCTED — the one live request tried was refused by the egress proxy.
Judgments are in the decision log row *"GIS ADDRESS SEARCH — GAPS 1, 7 AND 8"*.

## 52 · Lane GIS-46 record (PO GIS review gaps 4 and 6, PO "go", 2026-10-07) — version **2.558.5**

**What was wrong, reproduced first on PostgreSQL 16 (2.558.3/2.558.4):**

| Case | Before | After |
|---|---|---|
| Address search, City answers 401 / 404 / 503 | `500 SYS-INTERNAL` | 200, `reachable:false`, reason *rejected our key* / *map layer has moved* / *service had an error*; breaker 0 |
| Address search, `200 OK` + ArcGIS `{"error":{"code":498}}` | *"not answering"*, breaker moved to 1 | *rejected our key*, breaker 0 |
| Parcel check (`POST …/reconcile`), 401 / 404 / 503 on the first request | `500` | 200, `stopped:true`, `stop_reason_key` = the same reason |
| Pick's re-check refused | `500` | refusal with the reason |
| Parcel number already held, race (check passes, index refuses) | `IntegrityError` → 500 | *"This parcel already belongs to {{address}}."* (savepoint) |
| Parcel typed on Add premises, already held | accepted silently | the same sentence, on a person's form only |
| Any existing parcel refusal | *"That Parcel ID is already used."* | names the other property's address |

**Changed:** `apps/integrations/adapters/gis_city.py` (`CityRefused`), `gis_layer.py` (`refusal_reason`, metadata read guarded), `gis_parcels.py` (`REFUSAL_KEYS`, `stop_reason_key`), `gis.py` (search / pick / reconcile), `api.py` (refusal params), `seams/metering.py`, `gis_fixtures.py` + `gis_esri_fixtures.py` (four recorded refusing hosts: `key.`, `moved.`, `down.`, `token.gis.brazosbend.example`), `apps/metering/services.py` + `selectors.py`; `FindTheAddress.tsx`, `ConnectionDetailPage.tsx`; three new and two re-worded keys in all eleven catalogues.

**Proof.** Red first, pre-fix code: 14 of 16 cases failed (search 500 ×3, *not answering* + breaker 1 ×1, reconcile 500 ×3, `IntegrityError` ×2, no refusal on typed parcel, no address). Green: 34 cases on PostgreSQL 16 (`tests/test_def_int_9846_city_refusals.py`, `tests/test_def_met_9847_duplicate_parcel.py`), 51 + 188 neighbouring cases on SQLite, vitest 19 files / 309 cases + i18n 117. Browser at 1440, signed in as Dana: `08-qa/gis-gap4-6-2026-10-07/gap4-amber-{key,moved,down,token}-1440.png` and `gap6-parcel-taken-1440.png` (walkthrough `10-scripts/def_int_9846_def_met_9847_walkthrough.mjs`).

**Not changed.** Runbook 20's `reconcile_parcels` is still the stub the PO's 2026-10-07 ruling describes and calls nothing; it inherits this when bound to `gis.reconcile`. The breaker semantics are unchanged for silence (timeouts, no connection).

**Reds seen and not caused here.** `test_us_int_042_gis.py::test_the_middleware_puts_the_generated_policy_on_an_api_response` (CSP `frame-ancestors` gained `https://app.bynry.com` in `b82615107`, 2026-09-28); `connectorVocabulary.test.ts`'s integrations key total was red at the tip from `8d21ecd10` (one key added without moving the number) — moved to 462 here with both lanes' keys named; `G32` 21 unresolved keys and `G33` 10 over-cap messages, none in GIS or premises (e.g. `metering.import.parts_unwired` since `ab382ca64`, 2026-09-07; `payments.billing_read_unavailable` since `a52498914`, 2026-09-27).

## 53 · Lane GIS-B record (PO GIS review gaps 2 and 3, under the PO ruling of 2026-10-07) — version **2.560.1**, commit `3656e2eec`

**The ruling built under, verbatim (decision log 2026-10-07):** *"PO RULINGS — GIS: NO NEW NIGHTLY CODE; THE PARCEL CHECK WILL RUN THROUGH RUNBOOK 20, FIRST BY HAND AND ONLY LATER ON A SCHEDULE FOR ONE NAMED UTILITY; WHAT A NIGHTLY RUN DOES IS DEFERRED; THERE IS NO "GAP 5"."* No scheduler, beat entry or nightly task was added.

**What was wrong, reproduced first on PostgreSQL 16 (2.558.5):**

| Case | Before | After |
|---|---|---|
| Runbook 20 with a working Esri ArcGIS connection, no file | stops at step 1, *"Nothing has landed yet."*; City never dialled | asks the City's parcel check once (PREVIEW); *"The city sent 7 rows over 3 pages."*; matches, differences and premises with no parcel listed; every address difference *Never touched* (R28) |
| Same, the City refuses (401 / 404 / 503 / 200+error), sync switched off, bad page count | (never reached) | step 1 stops with the sentence — *The city rejected our key.* etc.; six steps *Never reached*; never a 500 |
| `POST …/reconcile` Preview at ~70 pages × 6 s | ~7 minutes inside a 60 s web worker → cut off | 3 pages by default, `?pages=N` to choose; *"Stopped after 3 of 70 pages."* on the report, the screen and the attempt row (Unconfirmed) |
| Preview where the City will not count its rows | — | *"Stopped after 3 pages; the city has more."* — no guessed total |
| Apply with a page limit | — | refused before dialling, *"Page limits are for Preview only."* (all or nothing, `BR-INT-072`) |
| Apply at a utility that has added Runbook 20 | **500** — the hand-off `{"source": "gis", …}` reached a UUID lookup | 200; the runbook is started and reads the hand-off as the City door (`DEF-INT-9850`) |

**Changed:** `apps/runbooks/seams/integrations_seam.py` (`city_parcels`, the one door to `gis.reconcile`), `apps/runbooks/definitions/gis_reconciliation.py` (the City door in step 1; steps 2–4 report the City check's own match and classes; class *Premise with no parcel*; input *City pages to read*; the hand-off read as the City door), `apps/integrations/gis_layer.py` (`walk(stop_after_pages)`, `Snapshot.complete/total_rows/total_pages`, `count_rows`), `gis_parcels.py` (`max_pages`, the *Stopped after* headline, `parcel` on each difference), `gis.py` (`max_pages`, `pages_or_refuse`, `MANUAL_PREVIEW_PAGES = 3`, two refusal keys), `api.py` (`?pages=` / `{"pages"}`), `gis_esri_fixtures.py` (`returnCountOnly`), two stale docstrings (`manifests/gis_esri.py`, `seams/runbooks.py`); `ConnectionDetailPage.tsx` + `integrationsEndpoints.ts` (the *Stopped after* line); four keys in all eleven catalogues.

**Proof.** Red first, pre-fix code: every new case that touches the change failed for the reason it names (step 1 *"Nothing has landed yet."*, `walk()` takes no `stop_after_pages`, `run()` no `max_pages`, no `city_parcels`, no page refusal, a 200 where a 422 was due); `DEF-INT-9850` red on PostgreSQL 16 as `ValidationError … is not a valid UUID`; the screen case red with the note removed. Green: `tests/test_def_int_9848_runbook_20_city_door.py` 44 cases on PostgreSQL 16 (incl. **Run ▶** dry with 2 pages through `POST /runbooks/{key}/runs`, premises and units byte-identical before and after, one preview attempt row), 213 GIS cases on PostgreSQL 16 across seven files, Runbook 20's own suite 35; vitest `src/features/integrations/` + `src/i18n` 24 files / 343 cases; `tsc` clean; G15, G31, G77 pass. **Browser at 1440, signed in as Dana**, recorded City (`gis.brazosbend.example`, 7 rows, 3 a page): `08-qa/gis-lane-b-2026-10-07/gap3-preview-default-whole-1440.png` (3 pages = the whole recorded City, no *Stopped* line), `gap3-preview-pages-1-stopped-1440.png` (*Stopped after 1 of 3 pages.* — the request URL rewritten in the browser to `?pages=1`, i.e. what a by-hand API call returns, drawn by the real screen; the screen has no pages box), `gap2-run-dialog-pages-1-1440.png`, `gap2-run-result-pages-1-1440.png` (*The city sent 3 rows over 1 page. Stopped after 1 of 3 pages.*), `gap2-run-dialog-whole-1440.png`, `gap2-run-result-whole-1440.png` (*The city sent 7 rows over 3 pages.*; 16 premises with no parcel queued, 6 new values and 1 conflict — *Riverbend Twp* vs *Riverbend* — never touched). Walkthrough `10-scripts/def_int_9848_9849_parcel_check_walkthrough.mjs`. Two defects of our own were found by the walkthrough and fixed before push: *"over 1 pages"*, and *Ambiguous match 16* counting premises nothing matched.

**How a person runs the parcel check by hand today:** (1) Settings → Integrations → Esri ArcGIS → *Nightly parcel check* → **Preview** — reads up to 3 pages, writes nothing, says *Stopped after 3 of N pages* when the City has more (`POST /integrations/gis_esri/reconcile?pages=N` for another number); (2) Runbooks → Templates → add *GIS reconciliation* → its page → **Run ▶** → *Dry run*, optionally *City pages to read* → Runbooks → Run history → the run.

**Not changed / left open.** What a scheduled or nightly run does (report or update) — deferred by the PO and not built. An **Apply** over the web still reads the whole register and can outlast the 60 s worker at Ann Arbor's size (all or nothing; stated in `gis.reconcile`'s docstring and the decision log). A connection naming no layer still makes `POST …/reconcile` a 500 (`GisRunRefused` uncaught on that route; Runbook 20 catches it) — not filed separately, noted here. The *Nightly parcel check* label still says *Nightly*.

**Reds seen and not caused here.** `test_us_int_042_gis.py::test_the_middleware_puts_the_generated_policy_on_an_api_response` (CSP `frame-ancestors` gained `https://app.bynry.com` in `b82615107`, 2026-09-28 — also reported by section 52); `test_us_rbs_015_conformance.py::test_us_rbs_015_every_money_kpi_tile_declares_its_basis` (seven payments-runbook tiles; the case dates from `8429ef219`, 2026-09-07); `G115` (`leak_alert.py:846` imports `apps.notifications` outside a seam); `G32` 21 / `G33` 10 / `G13` / `G20` findings, none in GIS, runbook 20 or these keys.

## 54 · Lane LEAVE-GUARD record (PO report + PO ruling (a), 2026-10-07) — version **2.560.2**, commits `52dc6985f`, `e02ba1056`, `64c42379f`

**The report, relayed by the PO:** a clerk two or three steps into a move-in clicked a side-nav item and lost everything. **Cause, confirmed by the PO:** *"The move-in was opened from a service request, where automatic save is off, so the work really was lost."* **Ruling, verbatim:** *"lets start with this and also tell user if they leave work will not be saved - (a) Popup on all 45. "Save as draft" only on the 6 that can keep a draft. The other 39 say "Leave without saving? · Stay""*. Track: **maintenance** (people use every one of these screens today). Defects filed before the fix: `DEF-SHL-10001` (no screen asks before it is left) and `DEF-CUS-10002` (move-in from a service request does not autosave; a failed autosave is silent).

**Reproduced first, in a browser at 1440 on build 2.559.1:** Move-in through *Edit* on SR-26-0001, date typed, two steps forward, side menu → Accounts opened with no question, Edit reopened → date empty. Add premises step 2, address typed, side menu → left with no question. Photos: `scratchpad/po-shots/leave-guard/before/`.

**Built:** `components/LeaveGuard.tsx` (react-router `useBlocker` + `beforeunload`), mounted by `WizardFrame` and `WorkflowRunner` — **45 screens**: 36 on the frame, 9 import runs. *Save as draft* on Move-in, New connection, Transfer, Move-out, Disconnect and Service request capture, each writing the store it already had (`wizard_parks` as a draft; the request's own move-in form; the request itself). The 39 others: *"Leave without saving?"* / *"Your work will not be saved."*. Move-in on an undecided request now writes `PUT …/move-in-form` a moment after each change — never a park row (`DEF-CUS-9731`); a failed autosave says *"Changes not saved yet."*. The nine judgments, the full list of 45 and the figures are the decision-log row *"LANE LEAVE-GUARD (LANE JUDGMENTS)"*.

**Proof.** Tests written red first: `LeaveGuard.dom.test.tsx` (10 — under a real data router with a side-nav link outside the frame; 6 red with the guard removed, Complete and Save & exit red with the deliberate-exit rule removed, the rail step change red when `?step=` is treated as leaving), `leaveGuardInventory.test.ts` (4 — red when either shell drops the guard or a seventh flow offers a draft), `useMoveInEdit.dom.test.tsx` (+2 — red at 2.559.1: no `PUT …/move-in-form` was sent). Browser walk `10-scripts/leave_guard_walkthrough.mjs`: **22 of 22** at 1440, photos and README in `scratchpad/po-shots/leave-guard/`. Regression walk: Park (New connection), Save draft & exit (Move-in on a request, standalone Move-in) and a request's last-step save all leave with no popup. Wider suite: 8,481 passed; the reds are listed below.

**Not changed / left open.** The customer portal's own step flows (the ruling is about clerks). Five of the 39 carry a *Save draft & exit* of their own (New plan, Edit plan, New tax, New discount, Rate schedule) — they get the no-draft popup as ruled; offering *Save as draft* there would be a new ruling.

**Reds seen and not caused here** (each red on the branch tip `1ad5615cc` before this lane, run in a clean worktree): `wizardRailCensus.test.ts` (DEF-CUS-5071 census, file last changed `e9c5e15df` 2026-10-04), `ConfirmDialogTier.dom.test.tsx` call-site census (40 vs 38, `d34c07d5b` 2026-10-04), `refundsLegacyRoute.dom.test.tsx` ×2 (`61e640394` 2026-09-23), `ReturnedPostBanner.dom.test.tsx` ×1 (`35f3cf079` 2026-09-23); gates `G13` (unwired props in RateScheduleWizard / moveReadsCapture, red at the same tip) and `G33` (refusal lengths in integrations/ledger/rating keys). `wizardPark.dom.test.tsx` went red on this lane's first draft (3 cases) and is green after `e02ba1056`.

**Tell the reporter:** look in build **2.560.2**.

## 54 · Lane GIS-D record (PO GIS review gaps 9–14 and Lane B's three leftovers, 2026-10-07) — version **2.560.3**

**Scope as narrowed by the PO the same hour** (decision log *"PO RULING — GIS LANE D MUST NOT CHANGE THE ASSET MAP TAB OR THE WORK ORDER MAP"*): neither map, `basemap.ts`'s behaviour, `getAssetGeo` / `ASSET_MAX_PER`, `getWorkOrderMap` nor the backend reads behind them was edited. Both maps were photographed at 1440 on the tip and again on the change — pins, a pin's popup, the click-through to the asset / the work order, the work map filtered by area — and the fourteen photos are **pixel-identical except the build number in the sidebar** (`08-qa/gis-lane-d-2026-10-07/maps/before-*` / `after-*`; walkthrough `10-scripts/gis_lane_d_maps_walkthrough.mjs`, whose printed lines are identical before and after).

**Reproduced first, in a browser at 1440 on 2.560.1 against a local API** (`10-scripts/gis_lane_d_screens_walkthrough.mjs`, four worlds: no City · working · broken · no layer):

| Gap | Was | Now | Proof |
|---|---|---|---|
| 9 (`DEF-MET-10003`) | No City GIS, and the property Overview still drew *Parcel*, *On the map*, *Checked against GIS*; the unit Overview *On the map*; Edit premise the latitude/longitude boxes | Drawn only where a City GIS is in use (`GET /integrations/gis_esri/state` ≠ `none`); nothing deleted — a box not drawn is not sent | `before-nogis-premises-overview` vs `after-nogis-premises-overview` (only *Import reference* left) · `after-working-*` (all back) |
| 12 (`DEF-INT-10004`) | Broken and never-set-up read the same off the Settings page | `broken` keeps the fields and adds one line: *The city connection is not working.* / *The city layer address is missing.*; not set up says nothing on a premises screen | `after-broken-premises-overview`, `after-nolayer-unit-overview`, `after-broken-edit-premises` |
| leftover a (`DEF-INT-10005`) | Preview with no layer address: **500**, and an attempt row left running | **409**, *The city layer address is missing.* under the Preview button; no run row | `before-nolayer-esri-preview` (500 in the walk's log) · `after-nolayer-esri-preview` |
| 13 (`DEF-INT-10006`) | Census geocoder: *Save and test* → **Cannot be connected yet.** (no adapter bound) | Connects; *Test* geocodes one address and the card reads **Working**, 1 of 1 | `before-nogis-census-after-connect` · `after-nogis-census-tested` |
| leftover b (`DEF-INT-10007`) | *Nightly parcel check*, "every night" | **Parcel check**, in all eleven catalogues (`integrations.provider.gis_esri.operation.reconcile_parcels`) | `after-working-esri-connection` |
| leftover c (`DEF-MET-10008`) | *Parcel* labelled the City's parcel on Add premises AND the import key (`external_ref`) on the Overview, Edit premise and New Connection | `external_ref` reads **Import reference** everywhere; *Parcel* only over `gis_parcel_id` (now also drawn on the Overview where a City is in use) | `after-*-premises-overview`, `after-*-edit-premises` |
| 14 (`DEF-INT-4267`) | already fixed at `e7750e9d9` (2026-09-06) and left *open* | closed with proof: signed in as **Sam Reyes, Billing Clerk**, the address search answered **200 with 4 candidates**, on the tip and on the change | `before-working-clerk-address-search`, `after-working-clerk-address-search`; the two route cases in `test_us_int_042_gis.py` green |
| 10 (`DEF-INT-10009`, `DEF-INT-7430`) | The middleware test red since **2026-10-05** (`9b6b8ae50`, `DEF-INT-9707`), misdated by two lanes to `b82615107` | The HEADER was right; the test now pins *base policy + app origins on `frame-ancestors` only*. A new case pins that a tenant's own tile host is ADDED to `img-src` and nothing else moves. **Static host: stopped and reported** — the baked `<meta>` policy caps every header, so a tenant's own tile server loads there only through a tile proxy (changes `basemap.ts` — out of scope) or a per-tenant header from the host (CDN code — PO: no lock-in). `DEF-INT-7430` (b) stays open | `test_gis_lane_d_census_and_city_state.py::test_a_tenants_own_tile_host_is_added…` |
| 11 (`DEF-MET-4301`) | — | **Not done**: the only maps are the two the PO took out of scope; the premises screens draw no map (PO 2026-09-08). `DEF-MET-4301` stays open | — |

**Changed:** `apps/integrations/gis.py` (`city_state`, `REFUSAL_NO_LAYER`, `REFUSAL_CONNECTION_BROKEN`, the no-layer refusal before the run row), `api.py` (`GET …/state`), `adapters/geocoder_census.py` (new) + `adapters/__init__.py` (twelfth adapter), `census_fixtures.py` (new, `.example` only), `manifests/geocoder_census.py` (real default address), `manifests/gis_esri.py` (*Parcel check*), `apps/runbooks/seams/integrations_seam.py` (the no-layer sentence); `07-frontend/src/features/metering/CityGis.tsx` (new: `useCityGis`, `CityGisNote`), `PremisesDetailPage.tsx`, `PremisesListPage.tsx`, `UnitDetailPage.tsx`, `UnitEditModal.tsx`, `customers/NewConnectPremiseStep.tsx`, `NewConnectReviewStep.tsx`, `api/endpoints.ts`; seven keys in all eleven catalogues; `BR-MET-1163` stamped.

**How to test the Census geocoder by hand** (in `adapters/geocoder_census.py`'s docstring): `curl -sS 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address=4600+Silver+Hill+Rd%2C+Washington%2C+DC+20233&benchmark=Public_AR_Current&format=json'` → `result.addressMatches[0].coordinates ≈ {x: -76.92744, y: 38.845985}`; then Settings → Integrations → Census geocoder → Connect → Test. The live call was NOT made from this sandbox (egress proxy) — the in-product proof used the recorded `.example` host.

## 55 · Lane ACH-RETURN record (PO ruling 2026-10-07 — a billing clerk may mark an ACH payment returned) — version **2.561.0**, commits `2747551e3`, `33a4665b2`

Its own change request is `CR-175-BRC10` (`12-governance/change-requests/CR-175-BRC10-clerk-marks-ach-returned.md`), which carries the build, the proof and the before/after of the returned-payments process; this section is the pointer the coordinator's lane rules ask for. Defects: `DEF-PAY-10010` (fixed), `DEF-PAY-10011` and `DEF-PAY-10012` (filed, open).


## 56 · Lane E2E-FIXES record (fixes from the 2.560.3 end-to-end walk, `08-qa/e2e-2026-10-07/README.md`) — versions **2.561.1**, **2.561.2**, **2.561.3**, commits `323dae76a`, `98f51031d`, `d4daa1f32`, `8f845fa87`

Maintenance (`22-product-maintenance-process.md`): each was reproduced by the walk on 2.560.3 (its photos are the "before"), fixed red-first, and walked again at 1440 on a local stack only (SPA built with an empty API base, own PostgreSQL 16, own Redis, the recorded `a2.gis.example` City). Judgments are in the decision log, *"FIXES FROM THE 2.560.3 END-TO-END WALK"*, items 1–9.

| Defect | Was | Now | Proof |
|---|---|---|---|
| `DEF-MET-10013` (2.561.1) | *2670 Sequoia* drew two identical rows; picking the unit gave the property the unit's point — and every pick was dropped one render later, so the property was written as typed | Row reads *2670 Sequoia Pkwy · Unit A*; property P-00080 got the building's 42.300000, -83.790000; unit **A** got 42.300010, -83.790010 and key `…-000A`; *Found on the city map* holds | 4 + 1 front-end and 5 backend cases red first; walk 5/5 (the review reads *1 — labeled A*); read back on PostgreSQL |
| `DEF-CUS-10014` (2.561.2) | A change typed within 0.8 s of the request's move-in loading was never autosaved | The starting point follows the loaded form until the clerk first acts, then freezes; the first change is sent 0.6 s later | dom case red first; A8 with NO pause, twice: save sent at 617 ms, date kept after *Leave without saving*; `leave_guard_walkthrough.mjs` unchanged, 22/22 |
| `DEF-PAY-10015` (2.561.3) | *taken by Nobody named* on a US Payments payment | *taken by USPayments* | backend red first; walk C8 |
| `DEF-PAY-10016` (2.561.3) | A returned ACH said *The money cleared. Reverse it instead.*; status *Cleared* alone | *Already reversed.*; status *Cleared* · *Returned by the bank*; Mark returned disabled (2.561.0) | backend + dom red first; walk C10 |
| `DEF-PAY-10017` (2.561.3) | History NOTE *nsf* | *Returned by the bank* (catalogue key, eleven languages) | backend + dom red first; walk C10 |
| `DEF-INT-10018` (2.561.3) | USPayments header *Not tested yet* over 3 of 3 Working | *Working* after the first successful partner call; a refused call moves nothing | backend red first; walk C11 |

Not changed: the Asset map and the Work order map (PO ruling 2026-10-07); `DEF-PAY-10012` and `DEF-PAY-10011`.


## 57 · Lane GIS-CF403 record (PO ruling 2026-10-07 — every city map request carries `User-Agent: SMARTBillHub-GIS/<product version> (support@bynry.io)`) — version **2.561.4**, commit `56bad94ff`

Maintenance (`22-product-maintenance-process.md`). The PO reproduced it on the live server: Python's default agent → `403`, body `error code: 1010`; our own name → `200`. Defect `DEF-INT-10019` filed first (`d649e2c35`), tests red first at 2.561.3 (27 of 29 failing: the four transports handed `urlopen` a bare URL, every 403 classified *key*, no evidence on the run row), green after.

| | Was | Now |
|---|---|---|
| The request | `Python-urllib/3.x`, from three separate `urlopen` calls — and a fourth, `apps/metering/geocode.py` | `User-Agent: SMARTBillHub-GIS/2.561.4 (support@bynry.io)` from ONE function, `core/gis_http.py`; a test fails if any GIS/geocoder file calls `urlopen` itself |
| A 403 that is not ArcGIS JSON (`error code: 1010`, *Just a moment…*, empty) | *The city rejected our key.* | *The city's firewall blocked us.* — new key `integrations.gis.city_firewall_blocked`, eleven catalogues |
| 401 / 498 / 499 · 400 / 404 / 410 · 403 with ArcGIS JSON | key · moved · key | unchanged |
| The run row's provider error | empty | `403, error code: 1010` (status + first 200 characters; the scrub now keeps a provider's own *error code*) |
| The breaker | not counted | still not counted |

**Proof.** `tests/test_def_int_10019_gis_user_agent.py` 30 cases + the `DEF-INT-9846` suite: 48 passed on **PostgreSQL 16** (own cluster). fourteen GIS and integration neighbour files on SQLite: 361 passed, two reds not caused here (below). `tsc` clean (proved capable of failing); `FindTheAddress.dom.test.tsx` 43 passed. G15, G31, G89 pass. **Browser at 1440, local stack only** (`10-scripts/def_int_10019_gis_firewall_walkthrough.mjs`, recorded host `firewall.gis.brazosbend.example` answering 403 `error code: 1010`; every `/api` call asserted local): photos in the session scratchpad `po-shots/gis-cf403/` — `1-address-search-firewall-1440.png`, `2-parcel-check-preview-firewall-1440.png`, `3-run-detail-provider-error-1440.png`.

**Judgments:** decision log 2026-10-07, *"GIS-CF403 LANE — SIX JUDGMENTS"*. **Found, not fixed:** `DEF-INT-10021` (the Esri ArcGIS connection page is wider than 1440). **Reds not caused here:** `test_cr110__no_new_connector_declares_a_mapping` (gis_esri declares a mapping) and `test_us_int_013_the_coming_soon_cards_carry_their_wave_label`, both reading manifests last changed by `cbcca33b4` (2.560.3); G13 and G33's existing failures name rating, customers and other modules' keys, none touched here.

**DevOps:** deploy this build. Nothing else — no setting, no `.env`, no allow-list change. **Rollback:** redeploy 2.561.3.

## 58 · Lane SECURITY-SETTINGS record (PO ruling 2026-10-08 — *"go - build the last 5 passwords check"*) — version **2.562.0**, commit `71ff6a2d9`

**The report.** Ottumwa Water Works set values on Settings → Security and *"platfor does not behave as per values set here"*. Measured: eight of eleven settings were wired; three were not (decision log 2026-10-08, the PO ruling row).

**Was → now.** (1) *Password expires after* was stored and never read → a successful sign-in with a password older than the setting lands on the existing forced change (90-day policy: day 91 forced, day 89 normal; *Never* expires nobody; temporary passwords unchanged; a keep-me-signed-in renewal refused past expiry) — `DEF-IDN-10022`. (2) *"The last 5 passwords are blocked"* was false → the current password and the five before it are refused on every change, the sixth-oldest allowed; hashes only, `password_history` with RLS + FORCE (`identity/0010`), pruned to 5 — `DEF-IDN-10023`. (3) Every request slid the idle clock, so the bill run's 30-second poll kept a session alive for ever → a request sent while nobody has touched the page for a minute carries `X-Background-Refresh: 1` and slides nothing; idle expiry still refuses it — `DEF-IDN-10024`. (4) DevOps: read-only `manage.py client_ip_check` + runbook r7 for `TRUSTED_PROXY_COUNT`; allowlist logic unchanged.

**Proof.** `tests/test_def_idn_security_settings_true.py`: 9 cases RED on the unfixed code, all GREEN after; **PostgreSQL 16** (own cluster) 16/16 in the file including RLS ENABLE+FORCE and the cross-tenant probe, plus the G5 whole-schema sweep and identity 002/003/008 + CR-170: 53 passed, 1 skipped. SQLite neighbours 148 passed. vitest `backgroundRefresh.dom.test.ts` 4/4, `client.test.ts` green, `tsc` clean. Browser at 1440, local stack, every API call on 127.0.0.1 (`10-scripts/def_idn_security_settings_walk.mjs`): photos `po-shots/security-settings/1-forced-change-after-expiry.png`, `2-reused-password-refused.png`, `3-new-password-accepted.png`.

**Judgments:** decision log 2026-10-08, *"SECURITY-SETTINGS LANE — SEVEN JUDGMENTS"*. **Review:** ledger row 2026-10-08, HUMAN-REVIEW-PENDING. **Found, not fixed:** `DEF-IDN-10025` (`user_exists` names an unimported `ValidationError`, since 2026-08-16). **Reds not caused here:** `test_w0_models.py` three-roles and ten-services cases (red since `field_technician`, 2026-09-05, and `fire`, 2026-09-02).

**DevOps:** deploy; run migrations (`identity/0010`); before any utility uses Allowed addresses, run `manage.py client_ip_check` per runbook r7. **Rollback:** redeploy 2.561.5.


## 59 · Lane TAX-FILING record (PO ruling 2026-10-09, option (a), and PO "go for 2 and 3") — version **2.562.2**, commits `3bffe5813`, `ce7124f87`

Maintenance (`22-product-maintenance-process.md`). Judgments: decision log 2026-10-09, *"TAX-FILING LANE — SIX JUDGMENTS"*.

| Defect | Was | Now | Proof |
|---|---|---|---|
| `DEF-RAT-10027` | Settings › Accounting › *Authority accounts*, eyebrow *GL code mapping*, authority TYPED; on the tax *Account with the authority*, every number offered, "—" in the side panel, *From Settings › Accounting.* | *Tax filing accounts* (sub-tab, heading, pop-up eyebrow); *Authority* picked from the tax authorities, the server writes its name; on the tax *Tax registration no.*, only that authority's numbers plus unlinked ones, the choice repeated under the box and in *THIS TAX* → *Registration*; none held → *None held with Bexar County. Add one* → `/settings/accounting/authorities` | backend 4 red → 5/5 green (SQLite and **PostgreSQL 16**, own cluster); dom 10 red on the old code → 17/17; walk `10-scripts/def_rat_10027_10028_tax_filing_walk.mjs` ALL PASS |
| `DEF-RAT-10028` | A saved value not among a picker's options (retired number, undelivered due rule, missing liability account) read *Choose …* | The tax's own label | Reproduced first at 2.562.1: all six filing fields set → all shown (the one-page cause disproved, 128 accounts served); retired number → placeholder (red); fixed → shown. Dom case: 60 accounts, saved one 57th |

**Photos** (1440, local stack, every `/api` call on 127.0.0.1), session scratchpad `po-shots/tax-filing/`: `0-before-edit-step2-saved-values.png`, `1a-tax-filing-accounts-section.png`, `1b-add-pop-up-authority-dropdown.png`, `1c-tax-filing-accounts-after-add.png`, `2-filing-step-registration-number-chosen.png`, `3-filing-step-empty-names-authority.png`, `3b-leave-guard-before-tax-filing-accounts.png`, `4-edit-step2-all-saved-values.png`.

**Found, not fixed:** `DEF-RAT-10030` (a saved liability account since deactivated still reads *Choose an account*). *Add one* from a stepped-forward tax asks *Leave without saving?* first — the wizard's leave guard (PO 2026-10-07), working as ruled. **Reds not caused here** (gates run 2026-10-09): G98 eslint on `WorkflowRunner.tsx` and `newConnectDraft.ts` (last touched 2026-10-07 / 2026-10-06 by `52dc6985f` / `4a7a24732`); the other failing gates name no file this lane touched, except G135, whose stale-receipt list includes `rating/services.py` among 48 files changed since the backend receipt was taken.

**DevOps:** deploy this build; no migration, no setting. **Rollback:** redeploy 2.562.1.

## 60 · Lane DEF-RAT-10026 record (PO ruling 2026-10-09 — a service may hold two or more base codes for the same customer class, *"yes please do it"*) — version **2.562.1**, commit `0da54cd4b`

**Was:** New charge code → Base charge · Electric · BASE-E-OUT · Residential, with BASE-E already Residential, showed *"BASE-E already covers Residential."* under Customer class, disabled Continue, and Create refused (`rating.charges.base_already_covered`). Reproduced on the pre-fix build at 1440: `po-shots/two-base-codes/0-before-already-covers-refused.png`, and in `tests/test_def_rat_10026_two_base_codes_one_class.py` (4 save cases RED on the old code).

**Now:** the save-time overlap guard (`services._base_code_rules`, `base_codes_clash`, `base_code_clash`) is removed, with the step-1 warning (`useBaseCodeClash`) and `GET /charges/base-clash` (OpenAPI regenerated); keys `rating.charges.base_already_covered` and `rating.chargeCode.baseClash` retired via `i18n_fanin.retire`. Code strings stay unique. The help under *Base charge* now reads *"Each rate schedule picks one."* (eleven catalogues). The rate schedule's base-code picker shows *code · name* with the classes each covers. BR-RAT-088 / BR-RAT-1025 amended, the 2026-10-06 sentence SUPERSEDED inline.

**Billing — measured, unchanged:** every base reader passes the schedule's named code (`gather._base_answer`, `selectors._plan_base_total`, `seams.base_charge_for` for rate-change impact and the portal standing charge, `plan_reads._base_block`, `resolution.resolve_base_charge`). On PostgreSQL 16, one Residential account with W-RES $8.00 and W-RES-OUT $11.50 both Residential: schedule naming W-RES → $8.00, naming W-RES-OUT → $11.50, naming none → $0.00 + *Choose a base code*, never *"2 base charge codes"*.

**Proof:** PG16 — the new file 7/7 plus `test_def_rat_9797_9800`, `test_def_rat_8845`, `test_def_rat_9832`, `test_def_rat_5782`: 41 passed. vitest `chargeCodeTwoBaseCodes.dom.test.tsx` (renamed from `chargeCodeBaseClash`) and `rateScheduleWizard3.dom.test.tsx` 30/30, 3 cases shown RED on the pre-fix files; all of `features/rating` + `src/api` 1064 passed. `tsc` clean (proved able to fail). Browser at 1440, local stack, every API call on 127.0.0.1 (`10-scripts/def_rat_10026_two_base_codes_walk.mjs`, MODE=before/after/picker): `1-step1-no-warning.png`, `4-base-e-out-created.png`, `5a`/`5b` picker with BASE-E (Residential, Municipal) and BASE-E-OUT (Residential), `6-rate-schedule-picked-base-e-out.png`.

**Judgments:** decision log 2026-10-09 *"THE 2026-10-09 TWO-BASE-CODES RULING BUILT"*. **Review:** ledger AMENDMENT row 2026-10-09, PENDING. **Reds not caused here (all red with the pre-fix rating files too):** `test_def_154` ×4, `test_def_277` ×2, `test_def_rat_6960` ×5, `test_br_rat_088_base_migration` tc10, `test_br_rat_1040` tc3, `test_be11_openapi` tc02; vitest `adminOnlyReads.test.ts` (NewConnectPremiseStep reads `/settings/regional`, since `ad3bec69d` 2026-10-02).

**Rollback:** redeploy 2.562.0 — codes saved meanwhile stay; the old guard checks only new saves.


## 61 · Lane DEF-RAT-10029 record (PO report 2026-10-09 — *"Internal DB Codes are shown when user click on History button view details screen; please correct them"*) — version **2.562.3**, commits `c15599f0d` (server) and the screen commit that carries this section

**Was → now.** Plans & Rates → History (PLN-01.history, the same page from every Plans & Rates tab): *Who* was a user id → the person's name. *Change* was a field key and a database id (*account_type_id — → 01a0f27b-… and 89 more*) → one worded fact (*Minimum bill: $10.00 → $12.00*, *Tier 1 · Rate: $4.24 → $4.50 and 3 more*). *Batch* was a batch id → *Bulk change* / *Single change*; *Published by* showed the batch cell → the bulk change's person, or a dash. *Change details* was two raw JSON dumps → a Field · Before · After table of the same worded facts. A plan-version publish stored no before, so everything read as changed → it stores the plan as it read before, and its after carries the new version's terms. Rows already stored with no before say *Earlier values not kept* and list the saved values.

**Proof.** `06-backend/tests/test_def_rat_10029_history_words.py`: 4 cases RED on the old code, green on SQLite and PostgreSQL 16 (own cluster); neighbours `test_cr167_plans_round2`, `test_us_rat_plans`, `test_cr167_plan_fixes`, `test_def_rat_9510`: 68 passed. `RateChanges.test.tsx`: 3 new cases (no uuid in list or dialog text; *Field: before → after*; no-before rows) RED on the old screen, 19/19 green; rating vitest 995 passed; `tsc` clean (proved able to fail). Browser at 1440 on a local stack, API on 127.0.0.1 (`10-scripts/def_rat_10029_history_no_ids_walk.mjs`), old and new build against the same API: the old build shows a uuid on the list and on all six dialogs, the new one on none. Photos: `po-shots/history-no-ids/` — a plan tax change, a plan discount change, a charge code change, two rate schedule changes, and a row stored with no before, each list and dialog, before and after.

**Not covered:** tax and discount edits made on their OWN screens write `audit_log`, not this log, so they never appear on this page (only as a plan's change); a bulk change could not be photographed locally (the job store is not registered). **Judgments:** decision log 2026-10-09, *"PLANS & RATES HISTORY IN WORDS, NO DATABASE IDS"*. **Review:** ledger amendment 2026-10-09, HUMAN-REVIEW-PENDING. **Found, not fixed:** `DEF-RAT-10031` (a plan version's stored snapshot carries the replaced version's terms). **Reds not caused here:** `ConfirmDialogTier.dom.test.tsx` census (`NewConnectUnitsStep.tsx`, since `13a66a332` 2026-10-06); `test_be_list_export.py` setup errors (`AUTH-003` from `plan_versioning`, since `6bea16fcd` 2026-10-03).

**Rollback:** redeploy 2.562.2 — plan-version rows written meanwhile keep their before; the old screen prints them as JSON again.

## 62 · Lane HIST-TAXDISC record (PO rulings 2026-10-09 — History lists tax and discount changes, *"(a) Show them on History too"*; a plan's change history shows its taxes' and discounts' changes, *"but we should show the changes in tax and discount on plan change history"*; plan versions fixed going forward only, *"yes - old changes are not required (b) Fix it going forward only - this is okay"*) — version **2.563.0**, commits `e49d8ec8c` (server and screen) and the commit that carries this section

**Was → now.** (1) Plans & Rates → History listed plan, rate schedule and charge code changes only; a tax or discount edited on its own screen appeared nowhere on it → History lists them too (*Tax · City Utility Franchise Fee 2%* — *Rate: 2.00% → 6.00%*; *Discount · Senior 65+ discount* — *Value: 15.00% → 20.00%*), and the *What changed* filter offers *Tax* and *Discount*. Source: the tax and discount rows of the audit trail, read through the rating seam in ONE SQL union with the rate log — paged, sorted and counted in the database. The tax's and discount's own Audit tabs are unchanged. (2) A plan's Audit tab → *Changes underneath* said only *Edited* for a tax or discount, and a tax's new rate from a date (a new row in the tax's chain) never reached the plan at all → each row says what changed in History's words, and the chain is followed. (3) Publishing a plan's new version stored the terms of the version it replaced (v2 at $12.00 stored $10.00) → it stores its own; old copies are not rewritten; the plan's versions table (Overview) gains a *Change* column — *Minimum bill: $10.00 → $12.00* — and a copy from before the fix reads *Terms not recorded*.

**Proof.** `06-backend/tests/test_def_rat_10032_history_taxes_discounts.py`, 6 cases on PostgreSQL 16 (own cluster): all 6 RED at the tip `8e2cf4cde` (no tax or discount row on History; the plan Audit served no words; v2's copy held `10.000000`), all green now; `test_def_rat_10029_history_words.py` 4/4 green (UUID check unchanged). Vitest: `planDetail.dom.test.tsx` +2 and `RateChanges.test.tsx` 1 amended — 3 RED on the tip screen, 52/52 green; `tsc` clean (proved able to fail). Browser at 1440 on a local stack (API on 127.0.0.1, bundle built with an empty API base), `10-scripts/def_rat_10032_history_taxes_discounts_walk.mjs`: WALK PASSED, photos in the session's `po-shots/history-taxes-discounts/` — History all / Tax filter / Discount filter, Industrial's Audit with the fee's *Rate: 2.00% → 6.00%*, Small Commercial's versions *Minimum bill: $10.00 → $12.00*, Residential Standard with a copy rewritten to its pre-fix shape reading *Terms not recorded*. The first walk FAILED on a real finding: the fee's row read *Status: Active → Scheduled and 3 more*, the rate hidden in *more*; the figure a bill charges now leads a change.

**Judgments:** decision log 2026-10-09, *"TAXES AND DISCOUNTS ON HISTORY AND ON A PLAN'S OWN HISTORY …"* (seven). **Review:** ledger amendment 2026-10-09, HUMAN-REVIEW-PENDING (`selectors.py`, `plan_writes.py`, `plan_versioning.py`). **Not covered:** History's search still matches reason and record type only; old tax and discount changes leave History when the audit trail prunes them (`OQ-1340`); `DEF-RAT-5738` (the plan bound-change endpoint, on no screen) stays open; History's empty-state sentence still names plans and rate schedules only. **Rollback:** redeploy 2.562.3 — History loses the tax and discount rows and the versions table its *Change* column; copies written meanwhile keep correct terms and a `terms_recorded` key the old build ignores.
