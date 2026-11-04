# CLAUDE.md — SMARTBillHub (read every session)

Multi-tenant, self-serve **meter-to-cash + finance** app for **North American utilities of up to 40,000 accounts, run by at most 10–20 staff** — the PO's tiers **T7 (≤3,000) · T6 (3–10K) · T5 (10–40K)**, all three in scope now (PO ruling 2026-09-06, decision log *"THE ICP, CORRECTED THE SAME HOUR"*). ⚠ **THIS LINE READ *"small utilities/submetering (<3,000 connections, 1–2 staff)"* UNTIL 2026-09-06.** That ceiling was not wrong, it was the BOTTOM tier — T7 is still in scope — so this is the ceiling moving **3,000 → 40,000**; the **staff** half was simply false and is now **10–20**, ruled. **T4 (40–80K) and T3 (80–160K) are explicitly LATER** — *"we dont have to wory about T4 and T3 right now"* — and carry exactly one requirement, *"If we keep the architecture flexible we will able to later make the changes"*. ⚠ **THAT MAKES THE FLEXIBILITY LOAD-BEARING RATHER THAN TIDY, AND THE INSTRUCTION IS NEGATIVE: nobody may add a per-tenant cap, an unpaginated list, or an account maximum that would have to be removed when T4 arrives.** `NFR-5` (no hard caps anywhere), `NFR-3` (universal server pagination) and B6's design rule (*"no table, index, or code path may enforce a maximum account count per tenant"*) ARE that flexibility — they are the deliverable, not background. ⚠ **AND `NFR-3` IS ALREADY BREACHED IN AT LEAST FOUR PLACES THAT NAME THE OLD CEILING AS THEIR EXCUSE** — `GET /outstandings`, `GET /cheques`, the bank-rec batch list and their two front-end mirrors: correct at T7, **13× short of T5** (`DEF-PAY-4221`). ⚠ **AND THIS LINE QUOTED `/outstandings`'s OWN DOCSTRING AS THE EVIDENCE — *"Unpaginated ON PURPOSE … one row per DEBTOR at a utility under 3,000 connections"*, and *"it sorts in Python, not SQL"* — AND THAT DOCSTRING WAS WITHDRAWN ON 2026-09-23 (`CR-138` `P4`). THE READ NOW PAGES AND SORTS IN SQL.** Measured on real PostgreSQL 16 (`10-scripts/cr138_p4_debtor_cost.py`, median of 3 after a discarded warm-up): **2,046 debtors 3.089s / 2,041 statements → 0.232s / 13**, and **40,046 debtors 61.539s / 40,041 statements → 3.746s / 12**. ⚠ **A WEB WORKER IS GIVEN SIXTY SECONDS** (`docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`), so at the TOP OF THE ICP the old read was not slow, **it was killed before it answered** — and the 2,046-debtor figure is two thirds of the OLD 3,000 ceiling, so the sentence justifying the design was already 3 seconds of server time inside the tier it claimed to be correct in. **THE PREMISE WAS WRONG RATHER THAN THE CONCLUSION:** it argued that the KPI tiles must foot to the rows exactly (`US-PAY-013` TC-1) and a page would make them describe a page instead of the debt — but the tiles are a SQL aggregate over the whole filtered set whether a page is cut or not. ⚠⚠ **`DEF-PAY-4221` NEVERTHELESS STAYS OPEN, AND THE BREACH HAS MOVED RATHER THAN CLOSED: NOTHING ASKS FOR A PAGE YET.** The screen declares ten sorts, a search and four filters; the query honours three sorts and two filters, and cutting a page underneath the rest would be a live screen behind a broken control (law 2's mirror). The engine is built, measured and tested; the WIRING is `DEF-PAY-6271`. ⚠ **AND THE WITHDRAWAL CASCADES — TWO SIBLING READS STILL JUSTIFY THEMSELVES BY POINTING AT THE SENTENCE THAT WAS WITHDRAWN**: `payments/api.py`'s `/write-offs` (*"Unpaginated, deliberately, for the reason `/outstandings` is"*) and `payments/bankrec_read.py` (*"Unpaginated for the reason `/outstandings` and `/write-offs` are"*). **A justification by reference outlives the justification**, which is hard-won law 1 one indirection out: neither docstring is wrong about itself, and the thing both of them cite no longer says what they say it says. Re-argue each on its own facts or page it; do not read either as still carrying `/outstandings`'s reasoning. ⚠ **THE CAPACITY MATH NEEDS NO RE-RUN — 40,000 is exactly the top of T5 and is already the largest tenant B6 models**, so the existing model covers the whole ICP precisely; it is re-run only if T4/T3 are taken on, under `NFR-27`'s Eng-Lead precedent. ⚠ **THE PUBLIC HOME PAGE SHOWS NO PRICES (PO 2026-10-02, *"I dont want to display the pricing - we are going to revamp the procing"*; built 2.450.0, `DEF-TEN-4222` fixed).** It shows three SIZE bands — up to 3,000 / 3,000–10,000 / 10,000–40,000 accounts — and sign-up's size step shows no money. ⚠ **THIS LINE READ *"THE PUBLIC PRICING PAGE STILL TOPS OUT AT 3,000 ON PURPOSE … do not 'fix' those three bands"* UNTIL THAT RULING** — the deferral ended by the trigger it named. **The server's subscription plans still carry the old ranges and prices; nothing on screen shows them, and re-cutting them is the pricing-model work, not a screen fix.** Stack: **React · Django/Python · PostgreSQL 16**. Multi-service — **ELEVEN, not ten and not six** (BR-RAT-024 CONFIRMED-AS-AMENDED 2026-09-02; this line said six until 2026-08-16 while the platform seed carried ten, and said **ten until 2026-09-02**): Electric, Water, Gas, Sewer, Trash, **Storm water, Solar**, Broadband, **Thermal/Heat, Battery, Fire** — in that seed order. ⚠ **`fire` IS APPENDED AT POSITION 11 AND NOTHING IS RENUMBERED** (`CR-063`, PO 2026-09-02: *"We will need Fire as utility Service - Capacity based - this will behave exactly like trash"*, and *"we need it for one of the customer we want to go live"* — a real utility is being onboarded on it). **Fire is trash's arithmetic, not solar's: the size class picks the price and the COUNT multiplies it**, so one 2" line is `$12.00` and one 6" line with two 2" lines is `$60.00 + 2 × $12.00` = `$84.00`, on two bill lines — ⚠ **LAYOUT SUPERSEDED 2026-09-30, AMOUNT UNCHANGED:** PO *"per service"* makes it ONE fire line of `$84.00` (decision log *"ONE-TIME BILL: SIX ANSWERS"* (5)); re-checked on the code, still `$84.00`; the one-line layout is BUILT (2.411.3, `DEF-BIL-8151` — it read *"NOT BUILT yet"* until then). ⚠ **THAT SECOND FIGURE READ *"one 6" line with two private hydrants = `$110.00`"* UNTIL 2026-09-03, WHEN THE PO TOOK THE HYDRANT OUT — *"remove private hydrants from list"*, after *"hydrants are assets not utility service as of now"*.** `HYD` at `$25.0000` left fire's list, **fire is SIX sizes and not seven**, and **that warehouse now bills `$60.00` — `−$50.00` a month on a real customer.** It superseded a worked figure signed the day before, which is why the chain is written out here rather than left to be inferred. The six diameters and their prices did NOT move and fire still COUNTS. ⚠ **AND THE FRONT END TYPES THE SERVICE LIST OUT BY HAND IN TWO PLACES** — `SignupWizard.tsx`'s tick-list and `ratingShared.tsx`'s badge map — **so an eleventh service does NOT appear on screen on its own and it fails SILENTLY**: the row exists, the API serves it, `tsc` and every test pass, and the sign-up screen simply never offers it. That is hard-won law 2, and it is why `SignupWizard.test.tsx` now asserts **eleven**. Fire's six sizes and their prices are SEEDED DEFAULTS a tenant edits on Settings, never signed law — the going-live customer's own list is `OQ-1360` and is OPEN, and **removing the hydrant did not close it**: the PO took a row out, they did not ratify the six that remain. `OQ-1361` is ANSWERED IN BOTH HALVES — the hydrant is an asset (2026-09-03), and **a fire service gets a counted "fire line" item with a size from fire's own size list, picked on New Connection exactly like a trash cart** (PO 2026-10-02, option A; decision log *"THREE PO RULINGS IN ONE MESSAGE"*). ⚠ **THIS SENTENCE READ *"`OQ-1361` is HALF answered … the fire-LINE asset type is still `BR-AST-042`'s question"* UNTIL THE PO AUTHORISED ITS CORRECTION LATER THE SAME DAY** — a ruling that reached the register and not this line, the same rot as every pointer above.

## Where the truth lives
- `/04-docs/spec` — A1–A17, extracted from the design (what to build). Start: `01-screen-inventory.md`, `02-data-dictionary.md`.
- `/04-docs/decisions` — B1–B8, human/finance judgment (how to build). **B4 money-math + B5 golden-tests are ❄️ FROZEN — finance-signed 2026-08-08. The billing-code gate is OPEN; GT-1..61 are the billing-math contract.** ⚠ **THIS LINE SAID `harness 33/33` AS IF THAT WERE ENGINE PROOF UNTIL 2026-09-01 (DEF-2846), AND IT IS THE MOST-CITED NUMBER IN THE REPO. THERE ARE TWO NUMBERS AND THEY DO DIFFERENT JOBS.** `10-scripts/03-golden-verify.py` reports **33 checks** and they are **DOCUMENT self-consistency**: it recomputes B4/B5's own figures from fixtures and **imports no application code**, so it goes red when a document contradicts itself and **can never go red when the engine drifts**. The harness has always said so in its own docstring — *"it is not the rating engine"* — and the citations were what lied. What runs the ENGINE is `06-backend/tests/golden/`, and that is **engine-verified: 15 of the 61 signed GTs** (GT-1..11, 16, 24, 34, 47 — GT-34, the season-crossing split, joined 2026-10-01). **So roughly three quarters of the signed billing figures have no test that runs the engine.** Quote both, never one: **G64** (`g64_golden_engine_coverage.py`, identity in `g64_engine_verified_gts.txt`) recomputes the engine number, fails when a golden test arrives or leaves without moving the record, and fails any live document that quotes `33/33` without saying `engine-verified`. `--report` prints both sentences. ⚠ The two ❄️ FROZEN files still open with *"harness green (33/33)"*; that is TRUE of the harness, and correcting it is a **finance re-sign (HUMAN-GUIDE §6), never an inline edit** — so it stands, deliberately, and DEF-2846 holds it. PLACEHOLDER/UNVERIFIED strings still visible in those two files live in **superseded draft sections above the freeze banner** and each is stamped `SUPERSEDED (<ruling> → <rule that closed it>)` inline — a grep hit there is not a blocker (DEF-023; the Eng-Lead once reported R2's critical path finance-blocked on exactly that evidence). Changing a signed rule or figure needs a finance **re-sign via HUMAN-GUIDE §6**, never an inline edit.
- `/04-docs/03-contracts` — the stable interfaces (API A11, schema B2, enums A5, glossary A16).
- `/04-docs/02-decisions/14-ui-conventions.md` — **B14, the **THIRTY-SIX** binding UI rules, numbered 1–21 and 31–45 ⚠ **(rule 45 ratified 2026-10-21 — THE NATIVE FIELD APP HAS ITS OWN TYPE RAMP (title 22 · section 17 · body 15 · label 13 · micro 12) AND TOUCH STANDARD (56pt primary · 48pt any control · 8pt clear); one standard, two type ramps, never two design systems; scope `field-app/` only, web unchanged. THE POINTER MOVED IN THE SAME COMMIT AS THE RULE.)** ⚠ **(rule 44 ratified 2026-09-24 — THE DRAWING SAYS WHAT IS ON THE SCREEN AND HOW IT IS ARRANGED; OUR UI STANDARD SAYS HOW IT IS BUILT — spacing, sizes, the type scale, the tokens and the component kit — and it wins EVERY TIME, on EVERY screen, INCLUDING THE FRAME. PO: *"please use our ui, styleguide, spacing specifications. all the time , drawing is for how screen will look like you ahve to build it sing our ui standard"*. **It is rule 38 with its scope removed** — 38 gave the UI rules the win only for how a FORM is built, and a rule scoped to one kind of screen is read as permission everywhere else. **38 is NOT superseded; it is now 44's worked case for forms.** It does not contradict rule 41 either: *exactly* is about the drawn SHAPE, and rule 37 already made a drawn figure an illustration, so a spacing disagreement is nothing to escalate — the drawing never spoke to it. Ruled on Finance `P2.17`'s measured **65 off-scale values in 11 files, 25 of them in the app frame**, put to the PO as a product-wide change with the sidebar at 236px against a scale holding 224 and 240. ⚠ **`BR-SHL-001`'s OWN `240px`/`64px` ARE ON THE SCALE** — a signed figure stays signed and this licenses no change to one. THE POINTER MOVED IN THE SAME COMMIT AS THE RULE, FOR THE FOURTH TIME RUNNING.)** ⚠ **(rule 43 ratified 2026-09-20 — a piece of UI is built as a COMPONENT; standalone code inside a page is not reuse. Ruled after "use it" turned out to mean 120 lines inline in a 4,186-line page, importable by nothing. THE POINTER MOVED IN THE SAME COMMIT AS THE RULE.)** ⚠ **(rule 42 ratified 2026-09-13 — a screen is built from the drawing AS AN IMAGE; extracted text is an index, never the specification. PO: *"When you use images to create screens your accuracy is higher; hence dont create screens using only Text"*. It is rule 41's METHOD, and `10-scripts/pdf/pdf_render.py` is how — the PDFs live on the DEFAULT branch, not a working one. **THIS POINTER MOVED IN THE SAME COMMIT AS THE RULE, which is the only way this line has ever been right — three times running now**; rule 41 ratified 2026-09-13 — the product UI matches the blueprint EXACTLY, a screen is built to its drawn specification, and the only thing that reaches the PO is a drawing that contradicts a signed rule; rule 40 ratified 2026-09-12 — the page-head title is 32px on every screen. BOTH POINTERS MOVED IN THE SAME COMMIT AS THEIR RULE, which is the only way this line has ever been right — twice running now)** — ⚠ **THIRTY-NINE IS THE HIGHEST NUMBER AND HAS BEEN QUOTED HERE AS A COUNT SINCE RULE 31 WAS MINTED (corrected 2026-09-11, `DEF-4952`). RULES 22–29 WERE NEVER MINTED — zero mentions in B14, zero citations anywhere in the repo — and 30 was declined.** So this line has now been wrong SIX times, and the sixth is a different fault from the first five: those were STALE, lagging a ratification, and this one was a CATEGORY ERROR that was wrong the day it was written and got worse each time the maximum moved. A session counting on nine rules that do not exist will go looking for rule 25 and find nothing. **Count B14's own status table; never trust a number in a pointer, including this one.** (PO 2026-08-16: *"I want to see UI consistency every where - please make this part of repo"*).** ⚠ **This line said *twenty* until 2026-08-23 (DEF-609) while B14 held 29, and *twenty-nine* until 2026-08-30 while B14 held 30, and *thirty-one* until 2026-08-31 while B14 held 32, and **THIRTY-TWO until 2026-09-02 while B14 held 34**, and **thirty-four until 2026-09-03 while B14 held 35** (rule 35: a catalogue is written in its own language, not translated from English — PO, *"it sound like local person language and not mechanical translations of English"*) — **and THIRTY-FIVE until 2026-09-04, when rule 36 was ratified: the captured packs give layout and detail, `r10`'s `UI-RULES.md` gives the VISUAL STYLE, and the shared component kit is how you comply. That one was found by the PO looking at four shipped screens, not by any gate. ⚠ **AND THE NUMBER MOVED TO THIRTY-EIGHT ON 2026-09-10, WHEN RULES 37 AND 38 WERE RATIFIED TOGETHER — THE FIRST TIME THIS POINTER WAS MOVED IN THE SAME COMMIT AS THE RULE, WHICH IS THE LESSON BELOW BEING APPLIED RATHER THAN RESTATED A SIXTH TIME.** Rule 37: **a figure drawn in a wireframe is an ILLUSTRATION, never a fact to build to** — PO, *"Treat every number drawn in a wireframe as an illustration, never a fact to build to"*. It is what settles two frames of ONE blueprint drawing the same fact differently, which the *frame wins* ruling cannot, because both sides are frames: build the shape they agree on and ignore both sets of figures. Rule 38: **where a drawing and our UI rules disagree about how a FORM IS BUILT, the UI rules win** — PO, *"if youa re doing a form - go as per our UI rules"*. That is rule 36's split carried one step on, because side-by-side fields, help under an input and a footer's button order are CONSTRUCTION rather than layout, and each would change every dialog in the product at once on one screen's authority; what the form CONTAINS is still the drawing's to decide.** — it went stale TWICE over: rule 33 (⚠ **THIS SUMMARY READ *“a refusal sentence caps at five or six words”* UNTIL 2026-09-11 AND WAS NARROWER THAN THE RULE IN THREE WAYS** — it named a kind rule 33 does not have, gave one cap where there are FIVE, and dropped the clause that bites hardest. **The rule is: ON-SCREEN TEXT IS CAPPED BY WHAT IT IS FOR.** A LABEL or heading ≤ **3 words**, no sentence · a FACT ≤ **6 words** · an INSTRUCTION ≤ **6 words PER SENTENCE**, and *two sentences of six beat one sentence of twelve* · a CONSEQUENCE before an irreversible act ≤ 6 words per sentence, at most two, never cut below clarity · and **RATIONALE — why the product works this way, why a control is absent — is ZERO WORDS ON SCREEN**, it belongs in the code and the register. Ratified 2026-08-30; found by `CR-092` step 1 lane 1, which cited rule 32 because this line sent it there. **Read the rule, never this paraphrase**) never reached this line at all, and rule 34 (**one pair of words for *held here* and *in the books* — **Recorded** and **In the books**, everywhere, in all eleven catalogues**, `CR-060` C11) was ratified 2026-09-02. ⚠ **THE LESSON IS IN THE PATTERN RATHER THAN IN EITHER MISS:** this is the FIFTH time this one number has been wrong, every time in the same direction, because ratifying a rule and updating the pointer to it are two acts and only the first one feels like the work. A session that learned the rule set from this line alone would have met rules 33 and 34 as a review comment — **rule 32 (a screen has a description budget: one sentence per section, a stated absence CLOSED by default, no rule id or internal code in clerk-facing copy) was ratified that day after the PO said *"too much content - desctiption is too much for clark to read"* four times in twenty minutes** — rule 31 (no database id is ever the visible value of a field) was ratified by the PO that day in the words *"no Databse ID on screen - that is a rule"*, and the number 30 is deliberately unused because its proposal was declined in the same sentence** — and the nine it did not count include **rule 21: a new screen, component or piece of UI is written in Tailwind utilities and adds NO class to a stylesheet** (existing CSS shrinks only as a migration phase takes it). **G31 enforces rule 21**, so a session that learned the rule set from this line alone met it as a merge failure. ⚠ **AND THE MIGRATION CLAUSE IS PER FILE, WHICH THIS LINE HID INSIDE A PARENTHESIS UNTIL 2026-08-27 (DEF-974, and DEF-901's lane hit it the same day). ⚠⚠ AND FROM 2026-08-27 UNTIL 2026-09-12 THIS LINE THEN STATED THE WRONG MECHANISM — corrected by PO ruling, verbatim: *"Yes correct it"* (`DEF-GOV-5102`).** It read *"a Tailwind utility is emitted ONLY for a file listed in `07-frontend/src/styles/route-b-migrated.txt`. Write one in a file that is not on that list and … it renders as **nothing at all**"*. **IT RENDERS FINE.** `07-frontend/src/styles/tailwind.css` imports the utilities with `source(none)` and then declares `@source "../"`, so the compiler scans the WHOLE of `src/` and emits a utility for **any** file. Measured against the built stylesheet: of ten utilities each used in exactly one UNLISTED file, **ten of ten are emitted as real rules**. ⚠ **THE LEDGER GATES THE CHECKS, NOT THE CSS** — its own header says so: `G31` SKIPS a listed file and demands of an UNLISTED one that every class be declared by a stylesheet, while `routeBUtilities.test.ts` owns the listed ones and asks the stricter question. **So the real consequence of a utility in an unlisted file is a RED GATE at merge, and the fix is to ADD THE FILE TO THE LEDGER — never to reach for a stylesheet class**, which is what rule 21 forbids. ⚠ **THE WRONG VERSION COST THE OPPOSITE REFLEX, WHICH IS WHY IT IS WORTH THIS MUCH SPACE:** a lane reading *"renders as nothing"* hand-writes CSS, and `DEF-974`'s own repair did exactly that — it reused `.met-head-actions` rather than listing the file. **AND IT WAS WRONG THE DAY IT WAS WRITTEN, not stale:** `@source "../"` landed 2026-08-19 in `6bb0404cb`, EIGHT DAYS before the warning, which was an inference from a gate's complaint that nobody checked against a build. Both 2026-08-27 occurrences were real — they were fixes for OTHER UI defects that G31 would have refused at merge — and the reflex they taught was the wrong one. ⚠ **THE GENERAL LESSON IS THIS FILE'S OWN, TWICE OVER IN ONE DAY** (see the Screen IDs section on the module segment, `DEF-GOV-5012`): **where a rule restates what a tool does, name the tool and let a reader run it.** A paragraph describing a compiler's behaviour is a claim nothing re-checks, and it outlives the behaviour. Icons for row actions, one table type, two button sizes, danger tier on destructive commits, descriptions at **80%** (amended from r10's 66%). `05-prototype/r10-2026-08-16/UI-RULES.md` is its SOURCE, not its authority — B14 wins and every divergence is stamped there. **Read the status table before assuming a rule is checked: most are RATIFIED and UNENFORCED, because no gate in this repo reads rendered output.**
- `/05-prototype/r10-2026-08-16/SMARTBillHub.dc.html` — **THE clickable reference (PO ruling 2026-08-16: *"for this session we will be refering to r10 - as default"*)**. Layout/copy/flows/states only; DO NOT port its runtime. ⚠⚠ **AND FOR ANY MODULE THAT HAS A BLUEPRINT PDF, THAT SENTENCE IS SUPERSEDED AND r10 DROPS TO VISUAL STYLE ALONE — THE BLUEPRINT OWNS LAYOUT, COPY, **FLOWS** AND STATES (`DEF-GOV-5248`, PO ruling 2026-09-14).** PO, verbatim, having put our screen beside their drawing: *"ia have been telling yu constantly that you ahve to consider the pdf document i have proided - i have said so many time - then why you are pointing at r10?"* **They had, and the repo already agreed with them: B14 rule 36 ratified it on 2026-09-04** — *"UI screens layout and details you can folow from Screens that we capture from document, but style guide should be from r10 agreement"* — **and this line was never amended to match, for ten days.** ⚠ **THE WORD THAT COST IT IS `flows`.** Rule 36 hands LAYOUT AND DETAIL to the document and says nothing about flows, so this line went on handing flows to r10, and **a wizard's STEP COUNT is a flow**: the bill run drew six steps because `billRunShared.tsx` was built to r10's stepper — its own docstring says so, *"the prototype's stepper, in its order and its words"* — while the Billing blueprint draws **four**, argues for them in prose (*"Four words, each naming an act"*, p35), and carries a whole carry-over map on p86–p88 for converting the six into the four. **A lane obeying this line built the wrong shape and passed every check**, and four further step-2 lanes then built onto it. ⚠ **AND THE BLUEPRINTS ARE NOT ALL ON YOUR BRANCH.** Five were — Assets, Accounts, Premises & Units, Customer Portal, Plans & Rates — and **Billing's was not**, so a lane that went looking would have found nothing and fallen back here. It is now ON the branch as `05-prototype/04 Billing, As Built.pdf` (14,363,163 bytes, sha256 `137a2a48…`), which makes the anomaly the absence rather than the presence. **Check for a blueprint BEFORE reading r10 for any screen — `git -c core.quotePath=false ls-tree -r --name-only <ref> | grep -i 'pdf$'` across the refs, not just yours.** ⚠ **`-c core.quotePath=false` IS LOAD-BEARING AND THIS LINE PRESCRIBED THE COMMAND WITHOUT IT UNTIL 2026-09-23 (`DEF-GOV-6236`, found by lane P3-BACK).** Git **quotes a path containing a non-ASCII byte**, so `05-prototype/03 SMARTBillHub — Meter Reads blueprint.pdf` — an em dash — prints as `"05-prototype/03 SMARTBillHub \342\200\224 Meter Reads blueprint.pdf"`, **the line ends in `"` rather than `pdf`, and `grep -i 'pdf$'` does not match it.** Measured on the branch: the prescribed command finds **8** PDFs and the repository holds **9**. ⚠ **IT MISLED A LANE AND THE COORDINATOR ON THE SAME DAY, IN OPPOSITE DIRECTIONS** — the lane concluded the Meter Reads blueprint was missing and went looking for it elsewhere, and the coordinator reported its absence to the PO as a second finding beside a real one. **It has been on the branch the whole time, 4,779,186 bytes.** ⚠ **THE GENERAL SHAPE IS THIS FILE'S OWN LAW 7, FIFTH VARIANT: a check REPORTING ZERO — or here, EIGHT — OVER A SCOPE IT SILENTLY EXCLUDES.** The command is not lying; it is answering truthfully about everything it can see, and **a blind spot with no number beside it is indistinguishable from an empty one**. `G32` reported `0 unresolved` the same way over 21 live refusals. **Count what you found against what should be there, every time a search underpins a conclusion.** ⚠ **THE SHAPE IS THIS FILE'S OWN, FOR THE EIGHTH TIME: a ruling landed in B14 and the pointer to it did not move**, the identical mechanism as the rule-count line above and hard-won law 2's rotten hold. Ratifying a rule and amending every line that contradicts it are two acts, and only the first one feels like the work. ⚠ **`/05-prototype/UtilityBilling.html` — r9 — IS DELETED (DEF-610).** This line told sessions it was *kept* until 2026-08-23; `05-prototype/` holds r10 and four shared JS/CSS files and nothing else. **A1–A17 still cite it by path and were still extracted from it, so the spec still describes r9 screens that can no longer be opened** — which makes r10 the only readable reference and the staleness below permanent until re-extraction. (**DEF-524** is the same hazard in code: G14's hardcoded path outlived the file it named and reported PASS through six UI defects.) Read the design for the screen, the spec for the rules; **where A1–A17's screen description contradicts r10, r10 is right and the spec is stale — file it, don't follow it.** Re-extraction has not happened. Work/Workflows/expanded-Assets scope is still OQ-249 — a reference default is not permission to build them.

## Module map (each owns its tables; see B2)
tenancy · identity · metering (product name: Meter Reads; owns assets per B2 r4) · rating (product name: Plans & Rates) · billing · payments · ledger · customers · notifications (+ audit) · **work** (added 2026-09-03 in the commit that carries `metering/0044`, per `CR-070` §2(a) — PO ruling of the same day, verbatim: *"it will become the module itself"*; **the eleventh code module**, `portal` under `CR-068` being the tenth; it OWNS crews, technicians, skills, certifications, parts, work orders, templates, assignments, schedules, rules and labour rates, READS assets, connections, accounts, meter reads, areas and users through one read-only seam file per module in `apps/work/seams/`, and writes none of them — G78 fails a foreign write from its first commit. ⚠ The six Work tables (connections, connection services, work orders, templates, service characteristics, to-dos) were DECLARED in `apps/metering/connections.py` until 2026-10-21 and now live in `apps/work/connection_models.py` (`CR-187-BRC10` T-43, migrations `work/0046` + `metering/0078`, state-only — no SQL); the services that WRITE them are still in metering, which `16-work/03-field-map.md` §4 "REVISITED 2026-10-21" records as the remaining move). Docs modules add: platform-shell (0), assets, reports, integrations → 14 doc modules, 04-docs/05-modules/. Cross-module writes are forbidden; cross-module FKs are the reviewed interface set (B2 §2).

## Hard rules (never violate — see B8)
1. **Tenant scoping:** never touch a tenant table without `app.tenant_id` set; RLS `FORCE` is on. No cross-tenant queryset.
2. **Money:** stored to **4 decimals**, percentages to **6**, both DISPLAY 2 — PO re-sign 2026-08-22, verbatim: *"We already confirmed this - MOney 4 decimal, percentage 6 decimal , display both 2 decimal"* (supersedes this rule's original `NUMERIC(18,6)`; existing 18,6 columns stay lawful containers — the rule governs what is WRITTEN and what new columns declare). `CHAR(3)` currency; never float/cents. Round only at finalization/display (rule in B4). ⚠ **AND A UNIT PRICE IS THE ONE EXCEPTION TO *DISPLAY 2* — PO 2026-10-02, verbatim: *"Show unit prices with up to 4 decimals and keep every total at 2."*** A rate, a tier price or a per-unit charge shows as many places as it carries, up to 4 (`$0.0425`, `$8.9375`, `$0.10`); every AMOUNT stays at 2 (decision log *"THREE UI RULINGS FROM THE RATE-SCHEDULE SWEEP"* (1)). This line did not say so until 2026-10-03, and a walk reading it alone took Carl's `$8.9375` water tier rate for a breach (`DEF-BIL-9520`, closed not-a-defect).
3. **Consumption:** always with an explicit unit; never assume.
4. **Financial immutability:** no UPDATE/DELETE on issued invoices, invoice lines, payments, journal entries — corrections are new rows. ⚠ **NARROWED FOR EXACTLY THREE COLUMNS ON `payments`, AND FOR NOTHING ELSE — PO ruling 2026-09-02, verbatim: *"(a) Allow those fields to change"*** (`OQ-1322`, answering how a mistyped cheque number gets corrected when a payment row may never be updated; the lane recommended an append-only amendments table and the PO chose to widen the trigger instead). A payment's **`confirmation` (the cheque or confirmation number), `memo`, and `method_id` (the tender)** may now be UPDATEd in place, in any status, through the one named endpoint `POST /payments/{id}/correct-reference` — and the tender is refused once the payment is banked, because deposit batches group by day AND tender. **Everything else this rule names is exactly as frozen as it was:** every other column of `payments`, every other table above, and DELETE in every status. `payments/0014` is the ONLY place the database's allow list moves; widening it anywhere else is a new ruling, not this one. ⚠ **AND THERE IS NOW EXACTLY ONE SUCH NEW RULING — `payments/0051` (`CR-186-BRC10`, PO 2026-10-21).** Every payment is `posted` at entry and becomes `cleared` when its deposit batch is reconciled with the bank statement. The PO's words: *"uitlity will reconcile it bank statement that time it is cleared with clearing date"*, and *"cleared payment cannot be cancled"*. So a `posted` row may change **only** `status` → `cleared` (with its write-once `cleared_at`) or → `cancelled`, through a third list (`clearing`) that is read only when the old status is `posted`. `0014`'s two lists are unchanged byte for byte; `cleared` and `cancelled` are frozen; DELETE is refused in every status. Proved both ways on PostgreSQL in `tests/test_cr186_paycore_pg.py`. Any further widening is a new ruling again. ⚠ **The value a correction replaces then lives ONLY in `audit_log`, which is pruned on a retention schedule — AND `OQ-1340` IS NOW CLOSED THE WAY THAT SENTENCE ALREADY READ: THE ROW IS NOT EXEMPT.** PO ruling 2026-09-23, verbatim: *"keep the same rule s; when audit log is delete - it is deleted thats okay"* — option (b) of the three put to them. **So `audit_log` has ONE retention rule and no row type is exempt from it**, and the prohibition here stops being provisional: **no document, screen or docstring may describe this path as a permanent record of the old value** — not *until it is answered*, but **ever**. ⚠ **AND THE HONEST BUILD IS SILENCE RATHER THAN A DISCLAIMER.** B14 rule 33 puts RATIONALE at ZERO WORDS ON SCREEN, so a Correction screen says nothing about how long the old value survives; it simply never claims permanence. A screen that explains the retention policy breaks rule 33 while trying to obey this one. **THE WORKED CASE PUT TO THE PO:** Dana types cheque `4471` as `4417` on 8 August and corrects it on 9 August; under a twelve-month retention there is **no record anywhere** on 9 August the following year that it ever read `4417`, and a customer quoting the number on their own cheque matches nothing in the system. **The PO was shown that and accepted it.** ⚠ **THAT LIVE STRING IS FIXED — `P3.18` (`CR-137-BRC07`), 2026-09-23.** This line read *"ONE LIVE STRING IS NOW FALSE AND IS THE FIRST THING TO FIX … the key and its sentence move in the commit that builds `P3.18`"*. They moved: the `unavailable[]` code on every successful correction response is now **`amendment_history_is_not_a_permanent_record`**, renamed rather than reworded because a key named `_unruled` for a thing that is ruled is this repo's most-filed rot, and its sentence says the row IS pruned. ⚠ **AND THE PROPAGATION LIST MISSED THE ONE SURFACE A CLERK COULD SEE, WHICH IS THE LESSON.** `CorrectionRetentionNote` rendered that caveat ON SCREEN in all eleven catalogues, on the Correct-reference form AND its result panel, because `CR-059` task 41's row instructed task 42 to build it. Three registers, the wire and this file all named the propagation and **none of them named the screen** — it was recorded as a change-request row and read as a document rather than as code. It is **DELETED, not reworded** (rule 33: rationale is removed, never shortened), its two keys retired through `10-scripts/i18n_fanin.py`, and task 41's instruction reversed in the same commit. ⚠ **THIS CITATION READ `OQ-1330` FROM 2026-09-02 UNTIL 2026-09-14 (`DEF-GOV-5229`, PO ruling of that date: *"It's a money-path rule pointing at the wrong question, and it spread precisely because nobody filed it"*).** `OQ-1330` is a real METERING question — may a utility switch off the check that a reading's unit matches what the tariff prices in — so the citation never dangled and every id-existence check passed over it; it is `DEF-2804`'s shape, a real id read for a different real id, on a money path. **TWO LANES FOUND IT, ON 2026-09-02 AND 2026-09-04, WROTE IT IN PROSE IN THEIR OWN FILES, AND NEITHER FILED A ROW — so nothing counted it and it spread to 54 further citations on 50 lines in 30 files**, `openapi/schema.json` and p026 of the Billing PDF among them. All 54 moved on 2026-09-14; **41 occurrences that legitimately name the METERING question were LEFT, and changing one of those is the mirror-image defect.** ⚠ **The durable lesson is not the id: a finding recorded only in the file you happen to be in is a finding nobody can count, and it goes on spreading while two lanes both believe it is written down.**
5. **Ledger:** balanced pairs; only the ledger posting service writes journal lines.
6. **Idempotency:** bill runs + inbound payment webhooks (B2 unique keys).
7. Every money action writes `audit_log`.
8. **Addresses:** an address is stored on **`premises`** and NOWHERE else (`BR-MET-1161`, PO ruling 2026-09-04, verbatim: *"we are having addresses at one place now - Premises and Units -> then they flow to {Meters, Sub meter, assets} + { accounts} -> from there it flows to Routes and Cycles … so they will also draw addresses from same place that we we can maintain the integrtiy"*). A **unit refines a premises by LABEL, not by address**; every other entity — asset, service point, account, route, cycle, invoice, **work order**, portal page, map pin — **derives it by walking to the premises** and declares no address column of its own. `premises.lat/lng` travelled the same way, so a map and an envelope could not disagree — ⚠ **AND THAT COORDINATE CLAUSE, AND ONLY THAT COORDINATE CLAUSE, IS NARROWED BY `BR-MET-1162` (PO ruling 2026-09-08, built `CR-089` wave A): A UNIT MAY CARRY ITS OWN `lat`/`lng`, AND WHERE IT DOES THOSE ARE THE TRUTH FOR THAT UNIT.** PO verbatim: *"GIS data for unit might change and hence we have to have parcel ID and GIs details on Unit also"*. **THE ADDRESS HALF ABOVE IS UNTOUCHED — a unit still refines a premises by LABEL and still declares NO address column**, which is a cabin, a pad or a wing of a campus being somewhere its site office is not, never a second address. ⚠ **AND A FOURTH NARROWING, 2026-10-22 (`BR-MET-1202`, PO: *"location gps and gps set in system may differ"*): a field reading, a route photo, a field-added-meter proposal and a work order raised on site keep the PHONE'S `lat`/`lng` AT CAPTURE** — evidence of where the technician stood, never an address and never a correction of the premises' point; `lat`/`lng` only, field-scoped in `G85` exactly like a unit. **The fallback is part of the rule:** a unit with no point of its own reads its building's, and every screen showing a point says which of the two it is showing. **`G85`'s allow list is now FIELD-SCOPED for exactly this** — `HOME_FIELDS` permits `lat` and `lng` on a unit and refuses a `city` on it by name, because putting the whole class on the list would have opened the door the ruling deliberately kept shut. ⚠ **THREE EXCEPTIONS, EACH A DIFFERENT FACT RATHER THAN A SECOND COPY:** `customers.addresses` `kind='mailing'` (where the BILL goes, which for a landlord is another building) · `interruptions.location_text` (what a stranger typed — a report, not a record) · `tenancy.ServiceCentre.address` (the utility's own counter, which is not a property that takes service). ⚠ **`kind='service'` IS RETIRED** — it superseded B2 §2's second value, held 0 rows and was read by nothing, and a write asking for it is now refused BY NAME. **G85 fails a fourth home.** ⚠ **AND CLOSING THAT DOOR COST A SCREEN LINE NOBODY WOULD HAVE SEEN GO (`DEF-CUS-3653`)** — the account header composed `Austin, TX 78704` from the retired kind, so it would have returned null on every account forever with `tsc` and every test green. It reads `premise_locality` now, served by walking. **The lesson generalises: before retiring a value, grep for its CONSUMERS, because an absence is invisible to every check this repo has.**

## 🔒 Sensitive paths (amended by PO ruling 2026-08-09)
RLS policies · rating math (B4) · idempotency keys · ledger posting · money rounding · migration ordering · webhook keys. Originally stub-until-human; **PO 2026-08-09: "AI will do it; we will review it later as human."** AI authors these under the strongest machine gates (golden 33+245, isolation/RLS probes, balanced-pair tie-outs, idempotency tests, migration-guard), each file flagged `HUMAN-REVIEW-PENDING` with a row in `12-governance/09-human-review-ledger.md` (G7 enforces); none reaches lifecycle RATIFIED without a recorded human sign-off. The RULES they implement stay human/finance-signed (B4 ❄, B2) — AI implements signed law, never invents it.

**What counts as that sign-off (PO ruling 2026-08-11):** the PO reviews in the working chat session, and a ratification captured correctly in the repo IS the completed human review. Two parts, both required: **(1)** the rule and its worked number are put to the PO **in plain English with a concrete figure — never as an ID to go and look up** (standing PO instruction), and the PO rules; **(2)** the ruling is written into the ledger row verbatim with its date and the exact statements shown, and a test asserts the ratified figure so drift goes RED. **A signature covers only what was shown.** A file ratified on three presented decisions is not reviewed for a fourth that was never raised — that one stays flagged in the row and returns to the agenda. Write down what was shown, not merely that review happened.

## Screen IDs
Use A1 as the ticket vocabulary; never renumber. Canonical range now S1–S114 (S49–S60 provisional per A1 addendum, OQ-014; S61–S90 reserved; S91–S114 from design r8+). **ID grammar for everything else: US-/EP-/BR-<MOD>-#####, OQ-#####, GT-##, TC-#, IS-##, ADR-##### — FIVE DIGITS, ruled by the PO on 2026-08-31 in the words *"next question make them 5 digital"*** (said in reply to being told our own tooling could read only three and that we passed 999 some time ago). ⚠ **THAT IS A CEILING, NOT A SPELLING: NOTHING IS RENUMBERED AND NOTHING IS ZERO-PADDED — `OQ-291` is `OQ-291`, never `OQ-00291`.** Padding would move every citation in every register, docstring and test at once, which is the mass shared-file rewrite law 11 exists to prevent. ⚠ **AND THE THREE-DIGIT ASSUMPTION WAS WORSE THAN A LIMIT — IT WAS A SILENT MISREAD (DEF-2804).** These are SEARCH patterns, so `OQ-\d{3}` did not skip `OQ-1190`, it returned **`OQ-119`** — a different, real question — and a stub blocked on one question was recorded against another with nothing raising. It was live: `OQ-1166`, cited from a 🔒 rating-math file, read as `OQ-116` for two days (DEF-2820). **`BR-` is 37 ids from the same cliff** — `BR-RAT` stands at 962, `BR-MET` at 941 — and there the wrong answer is a rule citation pointing at the wrong rule on a money path. The pattern is `\d{3,5}(?!\d)` and the lookahead is load-bearing: without it `OQ-123456` reads as `OQ-12345`, the same bug one order of magnitude up. Defined once, referenced by ID (see HUMAN-GUIDE §2). ⚠ **AND FROM 2026-09-03 A QUESTION OR A DEFECT CARRIES ITS MODULE — `OQ-<MOD>-nnnn`, `DEF-<MOD>-nnnn` (PO, verbatim: *"going forward OQs: register max - add prefix OQ-Wrk-nnnn to it so that we know which module it is; Same thing with defect - add prefix going forward Def-Wrk-nnnn"*).** One running number across the whole register (the register's maximum + 1, so ids stay unique), the module code in capitals like every other family, **nothing existing renumbered**: `OQ-INT-1470` was the first, `OQ-WRK-1490` and `DEF-WRK-3542` follow. ⚠ **THE TOOLING READS THE MODULE SEGMENT — AMENDED 2026-09-12 (`DEF-GOV-5012`), AND THIS LINE TOLD SESSIONS THE OPPOSITE FOR NINE DAYS.** It read *"THE TOOLING DOES NOT READ THE MODULE SEGMENT YET … a module-tagged id is taken BY HAND from the register's maximum and reserved in `14-id-reservations.md`"*, naming six files. **All six carry the optional `(?:[A-Z]{3}-)?` today** — `file_defect.py:129`, `gates/common.py:59` (`MOD_SEG`, used by `OQ_ID_RE` and `_OQ_ROW_ID_RE`; `DEF-3552` is the row that taught it, after 27 register rows were invisible to every gate), and `g08`, `g17`, `g38`, `g50`. **So use the allocator: `10-scripts/file_defect.py … --id-module CUS` allocates and appends `DEF-CUS-nnnn` correctly**, and taking a number by hand is now the *more* dangerous path, because `allocate.py` asks the REMOTE and a hand count reads only this checkout — which is how two lanes take the same number (law 11). The search pattern for these two families is `(?:OQ|DEF)-(?:[A-Z]{3}-)?\d{3,5}(?!\d)`. The decision log of 2026-09-03 records the reading chosen for *"register max"* and why. ⚠ **THE LESSON IS THE SHAPE, NOT THIS FIX: a caveat naming six files is a claim about six files and nothing re-checks it.** It is B14's rule-count rot in a different family — the fix landed, the pointer did not move, and the cost fell on every lane that obeyed the line instead of the code. **Where a rule restates what a tool does, prefer naming the tool.**

⚠ **AND FROM 2026-09-10 A CHANGE REQUEST CARRIES THE BRANCH THAT RAISED IT — `CR-<nnn>-<BRCnn>`, e.g. `CR-090-BRC01`, in its own file `12-governance/change-requests/CR-090-BRC01-<slug>.md`** (PO, verbatim: *"we are going to now work on 2 or 3 branches symeteniouly - so we dont want two branches write same CR number and when we merge we land into problem"*, and *"Ensure you assing branch Suffix to CR number"*). ⚠ **THAT IS A SUFFIX, NOT A RESPELLING: `CR-001`–`CR-089` KEEP THEIR BARE FORM AND NOTHING IS RENUMBERED** — the same reasoning that leaves `OQ-291` as `OQ-291`, because respelling eighty-nine ids moves every citation in every register, docstring and test at once. ⚠ **AND THE SUFFIX IS PROVENANCE RATHER THAN THE THING THAT MAKES IT UNIQUE.** Two branches can both reach for ninety and write `CR-090-BRC01` and `CR-090-BRC02`: the STRING is unique and the NUMBER is not, and a number is what a person says out loud and cites from a business rule. **Git cannot see that one** — one file per CR means the two touch different files and the index row is an append, so both sides merge cleanly and nothing goes red. So uniqueness comes from a **DISJOINT NUMBER BLOCK PER BRANCH** recorded in `14-id-reservations.md` before that branch starts (`BRC01` = `CR-090`–`094`, branch `claude/hi-0jmv62`; `BRC02` = `095`–`099` and `BRC03` = `100`–`104` unclaimed), from `10-scripts/allocate.py cr --verify <n>` at push time — which **cannot RESERVE**, it only removes the stale read — and from **`G17`, which fails a duplicate NUMBER even when the suffixes differ. That last one is the layer that ensures it.** The whole rule with its reasoning is `13-change-process.md` step 0.

## The build process — READ IT BEFORE YOU WRITE A LINE (PO ruling 2026-08-16)

**`04-docs/02-decisions/12-engineering-plan.md` → Addendum r11 is THE process.** It
supersedes §4's old five-step cycle. Every lane follows it; this pointer exists so
no session can miss it.

Seven steps, and the two the PO added are the two that were missing:

**0 · CHECK THE PACKET IS CURRENT.** Before assembling anything, read the four
places the repo changes under you — open questions, the decision log, the defect
register, change requests + the `surface_debt.txt` sentence — and ask of each:
*was this ruled since the doc I am about to build from was written?* Every
documentation failure of 2026-08-16 would have been caught here: a PO ruling that
reached every document and not the code for three days, and four surface-debt
sentences that named the WRONG FEATURE and sent a lane at work already shipped.
**Keep this human — nothing automated reads prose for truth.**

**1 · PACKET** — module folder + cited shared law + what step 0 found. Rules
quoted VERBATIM, never summarised.

**2 · BUILD, in four parts: (a) backend · (b) frontend · (c) tests + data ·
(d) prove it.** **2b is numbered so that skipping it is VISIBLE** — R2's central
failure was 66 stories with a finished engine and no screen, every deferral
honest and nothing adding them up; **step 6 refuses a story missing it.** 2c
writes test CODE for the cases §3 already declares — never authors cases after
the code. 2d breaks every guard FIRST, quotes the failure, then proves it by
clicking.

**W · WRITE BACK AS YOU GO — a continuous obligation, not a step.** The next
agent reads the repo, not your memory. A stale rule → amend it, dated, *before
building on it*. An unanswered question → mint it and stub, *before writing code
that would guess*. A defect → file it *before fixing it*. A judgment where the
rules ran out → decision log with its worked figure, *before reporting it to
anyone*. **Timing rule: before the thing that depends on it, never "at the end."**
On the day this was ruled, **117 of 132 commits touched a question, a decision or
a defect** — write-back is ~89% of the work, and the old process never mentioned
it.

**3 · SELF-VERIFY** (gates + checklist) · **4 · CLOSE THE RECORD** (decision row,
surface-debt count AND its sentence verified against the code, review-ledger row
stating what was shown to the PO in plain English with a figure — *before* review,
so the reviewer reads the repo the next agent will) · **5 · HUMAN REVIEW** ·
**6 · MERGE.**

## The maintenance process — WHEN THE PRODUCT EXISTS AND SOMEBODY IS USING IT (PO ruling 2026-09-10)

**`12-governance/22-product-maintenance-process.md` is THE process for that**, and it
exists because **there was none** — `r11` above is titled *"THE STORY→CODE PROCESS"*
and is entered from a story; the change process below is intake-and-classify. **Nothing
said how to fix a defect**, so beta work was being routed through the change process,
which is how our own misses start being recorded as the customer's new requirements.

**WHICH ONE AM I IN? One question: _can a user do this task in the product today?_
No → BUILD (r11). Yes → MAINTENANCE.** The test is about the USER and not the code —
*"is there already a file?"* gives the wrong answer for a new screen in an existing
module. **We classify; it returns to the PO only when the answer changes what a user
can DO or was PROMISED.** ⚠ **AND THE REDESIGN CASE IS NAMED ON PURPOSE: a live screen
redrawn end to end is MAINTENANCE**, borrowing exactly one thing from Build — the
drawing step. It feels like building (new wireframes, many waves, hundreds of lines)
and a lane that follows Build loses reproduce, blast radius, regression and the
reporter. **It has already gone wrong once, on the property Overview.**

**What Maintenance has that Build does not, and it is the first three steps:**
**REPRODUCE** it before reading code — never fix what you have not seen · **LOCATE**
the file actually mounted, not the one whose name matches · **BLAST RADIUS** both ways,
what else uses this AND what else USED what you are about to remove. Then the minimal
fix, proof against the reproduction in a browser, a regression walk of the neighbours,
**the eight accessibility questions for any customer-portal screen**, version and
rollback, and a close that **TELLS THE REPORTER WHICH BUILD TO LOOK IN** — a tester
who reports three things and hears nothing stops reporting, and the beta then produces
no signal at all. ⚠ **IN THE BETA A REPORT IS A DEFECT BY DEFAULT** (PO 2026-09-10:
*"CR is change in product, defect is product does not do what is expected"*) — the
routing table is `13-change-process.md` §1.

## The change process — WHEN THE AGREEMENT ITSELF CHANGES (PO ruling 2026-08-16)

**`12-governance/13-change-process.md` is THE process for that.** It is a separate
file from r11 above because it fires on a **different trigger**: r11 is read when a
lane STARTS A STORY; this is read the moment A CHANGE ARRIVES — a new requirement,
a reversal, a scope cut, a bug, a copy fix, a process change.

Nine steps: **0** capture (`CR-###` allocated at arrival, requester's words
verbatim, into `11-change-requests.md`) · **1** classify — and **when it is
ambiguous it is a DEFECT, not a change**, because filing our misunderstanding as a
"change" quietly converts our error into the customer's new requirement · **2**
what signed statement is being reversed, quoted, with its supersedes chain; a ❄️
FROZEN B4/B5 figure means **STOP** and re-sign via HUMAN-GUIDE §6 · **3** impact
across ten surfaces, including open questions **in both directions** and the demo
fixture · **4** what is already built and is now wrong — code shipped, data already
written, and **lanes building right now**, which the requester must be asked to
stop or let land · **5** size it and confirm in plain English with a figure, with a
deliberate **fast path** for anything touching no rule, no money and no data ·
**6** execute through r11, unchanged · **7** **VERSION** · **8** close, and state
the rollback before shipping.

**Step 7 exists because the PO said this step is the one usually skipped**, and the
repo proved them right: `07-frontend/package.json` read **`0.0.1` after 159 recorded
defects**, the backend carried no version at all, and nothing showed a version to a
user — so when two production defects were reported, neither the PO nor the product
could say which build they were looking at. Scheme `<release>.<change>.<fix>`
(**`2.14.7`**), one source of truth derived everywhere, visible on screen, recorded
on every CR and defect fix, **and a gate refuses a CR marked done with no version**
— because a step that depends on someone remembering is exactly the step that is
"many times not followed correctly".

**How the requester raises a change: however they like, in one sentence, whenever
they like.** No form, no template, no ID — *"you give me all these codes; im human
dont understand"*. **The burden of structuring is ours.** The one thing only they
can tell us is whether it is urgent or a thought.

⚠ **AND IT RUNS THE OTHER WAY TOO — EVERY REPLY, NOT JUST A RULING PUT FOR
SIGN-OFF (DEF-1931, 2026-08-28).** §6's plain-English rule names ONE channel — a
rule put to the PO for review — and **a rule that names one channel is read as
permission for every other.** So the review-ledger row asking for three guard globs
was written in plain sentences with its figure, correctly, while the status report
in the same hour carried ~40 defect ids, ~12 gate ids and words like *shadow run*,
*baseline*, *ratchet* and *blob*, in answer to a one-sentence question about what
was done. The PO's reply was *"I did not understand what are you talking about"*.
**Nothing can catch this** — no gate reads a chat reply, so the cost lands on the
human noticing and saying so, which is the exact effort the rule exists to save.
**A status update, an answer and a report are written the way a ruling is:** plain
sentences, a concrete figure where one matters, an ID only where they would use it
to look something up themselves. **The test: if a paragraph cannot be read aloud to
someone who has never seen the register, it is not finished.** The detail belongs in
the repo — that is what the repo is FOR — and the reply carries the meaning.

## Prime directive for implementing agents
Before coding a story, read its YAML frontmatter. `status: blocked`, a `blocked_by` OQ, or a rule marked OPEN/PROPOSED-unratified means: implement up to the boundary and stub the gap as `raise NotImplementedError("OQ-###")` — the OQ-ID in the code. NEVER resolve an open question by choosing a value. All questions route to the Product Owner via the working chat session (12-governance/01-open-questions.md). Every PR names its US-ID(s) first.
**Dependency rule (PO-confirmed):** before coding a story, ALSO read every story in its `depends_on` list and every journey file in `journeys` (08-qa/01-e2e/journeys/) — the handoff contracts there define what upstream leaves in the DB for you and what you must leave for downstream. Coding without them loaded is a prime-directive violation.
⚠ **AND READ THE STATUS COLUMN, NOT THE PROSE — A CLOSED QUESTION'S BODY GOES ON
DESCRIBING THE OPEN WORLD, AND THE BODY IS WHAT A LANE ACTUALLY READS (three
lanes misled in one evening, 2026-09-05; `DEF-WRK-4030`).** A register row has a
STATUS field and a BODY. Only the status is treated as authoritative, so only the
status gets edited when a ruling lands — and the body, which is where the
instructions live, rots silently. `OQ-WRK-1496` read **CLOSED** in its status
column while its own body still said *"no retention period is written anywhere"*
and *"`retention_policy()` raises naming this question"*, every clause of which
was false; a briefing written from that body told a lane to build a stub that
would have deleted a PO ruling from four documents. The same evening,
`OQ-WRK-1490` and `OQ-WRK-1491` were closed while the epic, the execution plan
and the story frontmatter all still said OPEN and still instructed a stub —
**the exact opposite of the rulings, which say each becomes a deliberate absence
rather than a stub awaiting an answer.**
**So: the status column decides, and a body that contradicts it is stale until
proved otherwise.** If they disagree, check `12-governance/02-decision-log.md`
and the module's `02-business-rules.md` — a real ruling is always in both — and
**amend the body before you build**, per step W.
⚠ **AND CLOSING A QUESTION IS A FAN-OUT, NOT A STATUS EDIT.** One ruling on
2026-09-04 left EIGHT surfaces saying different things: the register row's status,
the register row's body, the decision log, the module's business rules, the change
request, the epic, the execution plan and the story frontmatter. Closing a
question means walking all of them in the same commit — the same discipline the
change process already applies to a change, for the same reason.

## Before writing billing code
The B5 freeze is **DONE** (finance/Product Owner, 2026-08-08) — that precondition is closed, not pending. What remains: resolve every **blocking** item in `12-governance/01-open-questions.md` (the live registry; A17 scoreboard is the historical view) before coding the affected rule. Guesses in billing become silent production errors.

## Build order (from README)
Shell+tokens → Settings/lookups → Plans&Rates → Premises/Units → Assets (meters) → Accounts → Reads(+estimation) → Billing run → Payments → Finance → Reports → Public (Pricing/Welcome/onboarding + provisioning). (Assets added per PO 2026-08-09; waves W0–W8 in B12 r3.)

## Hard-won laws (added 2026-08-10, from the first live deployment)

Nine defects reached a running product in one day. Each of these is one of them,
generalised. They cost a support cycle to learn; read them before repeating one.

1. **A comment claiming a guarantee is not the guarantee.** Model docstrings said
   RLS existed where none was written; three files described an OpenAPI CI-diff
   that no workflow ran; `tokens.css` said the webfont was "decided with the
   AppShell packet" and it was decided by nobody. If you notice a gap, file a
   story or a defect row — a comment is a note, never a plan.
2. **Built is not wired.** A component with an optional prop that nothing passes
   is dead UI: it renders nothing, every test passes, and the feature does not
   exist. Four defects in one day. **G13 enforces this now** — do not silence it.
   ⚠ **AND IT RUNS THE OTHER WAY, WHICH G13 CANNOT SEE AND WHICH COSTS MORE
   (DEF-CWP-3925, 2026-09-05).** The mirror of dead UI is a **live screen behind
   a dead control**: a button greyed out, a nav word that is a `<span>`, a card
   whose `Start →` carries *"opens with the next release"* — over a screen that
   is routed, tested and live. G13 asks whether a prop is passed; nothing asks
   whether a REFUSAL is still true. On 2026-09-05 the customer portal's front
   page had **two working doors out of eight**: five cards, the sign-in bar and
   three of the frame's four nav words were all still refusing over `CWP-002`,
   `CWP-008`, `CWP-011`, `CWP-013` and `CWP-015`, every one of them shipped days
   earlier.
   **The mechanism is a rule with a clock in it.** `CR-068` R3 says a control is
   held *until its screen lands* — correct the day it is written, and it rots
   silently on the day the screen arrives, because landing a screen and
   releasing the thing that pointed at it are two acts and only the first feels
   like the work. (That is hard-won law 12's shape for pointers, and B14's
   rule-count line has now been wrong five times for exactly the same reason.)
   **Every check passed over it**: 42 portal test files, 391 cases, `tsc`, every
   gate — because each wave tested ITS OWN screen at ITS OWN address, and the
   question *has the door started pointing at it* belonged to nobody.
   **So: WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES WHEN THE HOLD EXPIRES,
   in the same commit** — assert the destination by ADDRESS and by the screen id
   it opens, so the day the screen lands the suite goes red and names it. A hold
   with no such test is a promise nobody is keeping. And when you land a screen,
   grep for the control that was holding it.
   ⚠ **A FIXTURE THAT CANNOT TELL A WORKING LINK FROM A BROKEN ONE IS HOW IT
   HID.** The front page's test mounted the component bare inside a
   `MemoryRouter` with no `/:tenant/portal` route, so `useParams().tenant` was
   undefined and every address the page built came out `//portal/…` — a
   protocol-relative URL to another host, which reads as a perfectly good string
   to `toContain`. **Mount a routed component under the real path pattern**, or
   the one assertion that could have caught this cannot be written.
3. **Defaults fail closed.** `sslmode=disable` and `ALLOWED_HOSTS=localhost`
   each blocked a live deploy. The unsafe option must be the one you type.
4. **A template change never reaches a host that already has a `.env`.** Editing
   `.env.example` fixes nothing already deployed. Say so, every time.
5. **One generated file, committed once.** Two copies of the OpenAPI schema
   drifted within a day. One source; derive views on demand, never commit them.
6. **Diff the running app against `05-prototype/`.** No gate looks at rendered
   output. Nine defects were found this way and by nothing else.
7. **Prove a new guard goes RED before trusting it green.** Every check added
   here was first shown to fail on the defect it was written for.
   ⚠ **AND PROVE IT IN THE HARNESS THAT WILL RUN IT — that is the other half and
   it was missing until 2026-09-04 (DEF-GOV-3733).** `G85` and `G87` were each
   shown red, then green, by `python3 <gate>.py` — which exercises `__main__`
   and **never** the path `run_gates` uses. Both were announced green while the
   suite reported `gate crashed: AttributeError: module has no attribute 'run'`,
   twice, among 28 other failures where a new one is easy to miss. A red proof
   through the wrong entry point is not a weaker proof, it is **no proof of the
   thing that matters**. `_assert_registry_sane` now refuses a registered module
   with no callable `run` before any gate runs, so this particular version of it
   cannot recur — but the general form (a guard proved through a path nobody
   uses) has no mechanical cure and is what this clause is for.
   ⚠ **AND A RED PROOF AT BIRTH SAYS NOTHING ABOUT WHETHER ANYONE EVER READS IT
   AGAIN — WHICH IS THE FAILURE THAT ACTUALLY DOMINATED 2026-09-05.** Counted
   from the register: **20 of the 160 defects filed that day were checks that do
   not check** — one in eight — against 6 on the next-busiest day the repo has
   ever had, and 56 across its whole history. That is not a bad day, it is the
   shape this project fails in, and law 7 as written covered only the first
   morning of it.
   **Four distinct shapes, and only the first is what this law already says:**
     * **PROVED RED, THEN NEVER READ.** `G78`, the gate enforcing Work's module
       boundary, was red from the moment wave G landed, naming a file and a line
       number, and three lanes ran the suite past it. The message-kind guard and
       the seam-naming test had each been red for DAYS. Every one had been proved
       red at birth exactly as this law requires. **A guard is a claim only while
       somebody reads its output**, and a suite with 28 other failures in it is
       where a true one goes to hide.
     * **STRUCTURALLY INCAPABLE OF FAILING.** A superset check written as
       `if diff … | grep -q '^<'` under `set -o pipefail` is ALWAYS false, because
       `diff` exits 1 whenever files differ — so the guard reverted a sibling's
       work and reported success. `npx tsc` in a worktree with no local install
       fetches a newer TypeScript, aborts on a config error, and reports no type
       errors at all. `G5` ran the tenant-isolation suite on sqlite, where the
       guarantee cannot exist, and called 192 skips a pass.
     * **INCAPABLE OF PASSING.** The isolation fixture demanded `ALTER ROLE …
       NOSUPERUSER`, which only a superuser may issue — and a superuser bypasses
       the very policies the suite exists to test. Both ways of running it were
       impossible, in opposite directions, for three weeks.
     * **LOOKING AT THE WRONG THING.** A hold-expiry test asserted a screen was
       REGISTERED at an address while the router was mounting it somewhere else;
       both screens opened onto *"not built yet"* and every check passed. A test
       named after an assertion it does not make. A citation gate that refuses a
       repeated id and never asks whether the id was ever issued.
     * **REPORTING ZERO OVER A SCOPE IT SILENTLY EXCLUDES — and this one is the
       hardest to see, because the check is not lying.** `G32` resolves a
       refusal's `message_key` only where the helper is defined in the same
       file, and two modules import theirs from a sibling. It reported **0
       unresolved**, truthfully, of everything it could see — over **21 live
       refusals that reach a clerk as silence**, found only when a validator was
       put at the raise site instead. **A declared blind spot with no NUMBER
       attached is indistinguishable from an empty one**, so a check that cannot
       cover its whole subject must print what it skipped beside what it
       checked. The same shape, one layer down: a lane grepped a pytest stream
       for its exception mid-run, got zero, and reported success — it was
       measuring how far the run had got, because tracebacks print at the end.
   **What to do about it, and it is three habits rather than a tool:**
   **(1) READ THE FAILURES YOU DID NOT CAUSE.** Before you push, look at every
   red line in the suite and ask *was this red before I started?* — and if it
   was, say so out loud in your report, because that is how a guard red for days
   gets found. ⚠ **AND *WAS IT RED BEFORE I STARTED* IS A CLAIM ABOUT HISTORY,
   SO CHECK IT LIKE ANY OTHER CLAIM — `git log -S "<the failing symbol>" --
   <file>` ANSWERS IT IN ONE COMMAND (`DEF-CWP-4187`, 2026-09-06).** `G103` was
   fixed, went green, and was reverted forty minutes later by a sibling editing
   two neighbouring notes in the same file from a stale whole-file blob; it went
   red again on the exact fault it had just been fixed for. **Two lanes then
   reported it in good faith and in almost the same words — *"pre-existing red I
   did not cause"* and *"a red I did not cause… it was red before I started"* —
   and the second was the lane that had caused it.** Neither ran the one command.
   A third lane found it properly, by reading a failure it had not caused and
   then looking, and restored the row. ⚠ **THE DISMISSAL COSTS MORE THAN THE
   REVERT:** a revert is caught by the next reader, while two confident *not
   mine* reports tell every subsequent reader not to look — which is how a true
   red acquires the protective colouring of a known one. This habit exists to
   stop a red going unread, so **calling a red pre-existing WITHOUT DATING IT
   does the exact opposite of what the habit is for.** **(2) ASK WHAT WOULD MAKE THIS CHECK PASS WRONGLY**, not only what
   makes it fail — a check you cannot describe a false pass for is a check you do
   not understand. **(3) A CHECK'S OUTPUT MUST DISTINGUISH PASS FROM FAIL TO A
   READER**, not merely to an exit code: `--stat` was twice trusted to answer a
   question it cannot answer, and both times a lane following the rule correctly
   is what found the flaw.
8. **Every screen needs a story.** S1 shipped built to an endpoint contract
   because no epic owned it; the landing page was half-missing for a week.
9. **Write the ruling down when it is made**, in `12-governance/02-decision-log.md`
   — not at the end of the session. The conversation does not survive; the repo does.
10. **LAW 9 IS NOT ONLY ABOUT RULINGS — it is about everything said in chat that
    the next agent would need (PO ruling 2026-08-11).** Verbatim: *"during chat we
    discuss lot of thing, these are important rules and discussions, they need to go
    in repo if not next AI Agent or next chat will not pick it up and we will lose
    the context."*
    **The test is not "was a decision made" — it is "would the next agent, with only
    the repo, build the same thing?"** If no, it belongs in the repo BEFORE the reply
    that answers it. Four kinds and where each goes:
    | What was said | Where it lands |
    |---|---|
    | A ruling, a figure, an option chosen | `12-governance/02-decision-log.md`, verbatim + the worked number shown |
    | A rule the PO states or changes | the module's `02-business-rules.md` — CONFIRMED or SUPERSEDED with its date, and every citing document stamped the same commit |
    | A design constraint or a workflow shape | the epic's §1 text and §3 test cases, plus a journey in `08-qa/01-e2e/journeys/` when it spans modules |
    | A reason a thing is built the way it is | the file's own docstring — that is what a docstring is FOR |
    **A reply that explains something the repo does not say is a context leak.** It
    reads as progress and evaporates. This session alone produced: the five-phase bill
    run, the bulk-action requirement, base-only billing as a staff choice, the
    locked-at-issue snapshot, "the account derives its plan from the unit" — every one
    arrived as a sentence in chat and every one would have been lost. Cost of the rule:
    a few minutes per exchange. Cost of breaking it: the next agent rebuilds the wrong
    thing, confidently, and the gates all pass.
11. **IN A SHARED TREE, SCOPE THE COMMIT, NOT JUST THE `add` (DEF-160, 2026-08-16).**
    Many lanes work in one working tree, so **the index is shared too.** Staging four
    explicit paths and then running a bare `git commit` still commits **everything any
    other lane has staged.** Always: `git commit -F - -- <paths>` — it commits those
    paths from the working tree and leaves the rest of the index for its owner.
    **The check costs one glance:** git prints `N files changed`; if N is not the
    number of paths you named, you took someone else's work.
    **The recovery, verified:** `git reset --soft HEAD~1` puts the index back exactly
    as it was, the other lane's staged files included, then commit with a pathspec.
    Do it BEFORE pushing — after a push it is a revert, not a reset.
    **This is the THIRD occurrence.** The first two were `git add -A`, so the rule
    written from them names only ADD commands (`git add -A`, `git commit -a`,
    `git add .`, `git stash` — still all forbidden) and a lane could obey it perfectly
    and still sweep 25 files of a payment-plan wizard into a commit about governance.
    Nothing was lost and no gate objected; the damage is to the record, which is why
    it stayed invisible twice.
    ⚠ **AND THE FILE COUNT IS NOT ENOUGH — THE FOURTH OCCURRENCE LOST CODE (DEF-165,
    the same day).** A pathspec commit still takes the **whole working-tree content**
    of every path it names. So when two lanes have edited the SAME FILE, the second to
    commit silently reverts the first — its file count is *correct*, so the check
    above cannot see it. A customer-facing money fix (every bill charging $0.00 for
    base) left HEAD twelve minutes after landing, every test still passed, and the
    tree looked healthy. **So add one more step, and it is the only thing that found
    either occurrence: after pushing, re-read each file you changed FROM HEAD and
    confirm your own change is still in it** — `git show HEAD:<path> | grep <your
    marker>`, once per file. **To commit one file two lanes are editing**, build it as
    HEAD-plus-your-own-hunks and commit through `git commit-tree` against a private
    `GIT_INDEX_FILE`; that touches neither the shared index nor the other lane's work.
    ⚠ **SEED IT FROM THE REMOTE TIP, NEVER LOCAL HEAD** — `git fetch origin <branch>`
    then `git read-tree origin/<branch>`. A stale local base writes back a tree that
    predates other lanes' commits, which is mechanism two with extra steps.
    ⚠ **AND PIN THE TIP TO A SHA ONCE, BECAUSE THIS PROCEDURE HAS THE BUG IT CURES
    (DEF-306, 2026-08-19 — the EIGHTH occurrence, and the first caused by the
    recovery this law prescribes).** `git read-tree origin/<branch>` and
    `git commit-tree -p origin/<branch>` are two separate lookups of a ref that
    **any lane sharing this checkout can move between them** — `origin/<branch>` is
    a local ref and a sibling's `git fetch` updates it. When it moves, the TREE
    comes from one commit and the PARENT from another, and **everything between
    them is reverted by subtraction**: not by overwriting a file, but by building a
    commit that simply never contained those changes. A customer-facing CSS fix left
    the branch exactly this way, forty minutes after it landed.
    **It defeats every check above.** The file count is right — you named one path.
    Your own change IS present. `git show <commit>` shows only your hunks, because
    the reverted work is not in the diff at all; it is missing from the tree the diff
    is taken against. Nothing looks wrong anywhere.
    **So resolve the tip ONCE and use the SHA in both commands:**
    `TIP=$(git rev-parse origin/<branch>)` → `git read-tree "$TIP"` →
    `git commit-tree "$T" -p "$TIP"`. Then verify by SUBTRACTION rather than by
    inspection: `git diff --numstat "$TIP" <commit>` must show deletions only where
    you intended them. A commit-tree push that deletes lines you did not delete is
    this bug, every time.
    ⚠ **AND PINNING THE TIP DOES NOT PROTECT YOUR BLOB — IT ONLY PROTECTS THE TREE
    (DEF-1706 and DEF-1782, twice on 2026-08-27, and the second was a lane that had
    read this law).** The `commit-tree` procedure above pins the tip so the TREE and
    the PARENT come from one commit. **It says nothing about how old the CONTENT you
    are putting into that tree is.** You read a file, you work for twenty minutes,
    you pin the tip, you write your blob — and your blob is a whole-file copy of a
    version that predates a sibling's commit to the same file. The tree is built
    correctly from a stale ingredient.
    **It reverts by subtraction, so EVERY check in this law passes on it:** the file
    count is right, your own change IS present, `git show <commit>` shows only your
    hunks, `git status` is clean, and `tsc` and the suites are green — because the
    deleted work is not in the diff at all. One lane lost **44 locale keys** this
    way; another lost a defect-register row appended four minutes earlier.
    **What found both, and it is the only thing that did: read
    `git diff --numstat <pinned-tip> <commit>` AS ARITHMETIC, not as a glance.** On a
    two-row append, `2 insertions, 1 deletion` is not noise — it is a destroyed row.
    **The durable fix is not another post-push check: RE-DERIVE EVERY BLOB FROM THE
    PINNED TIP AT PUSH TIME.** `git show "$TIP":<path>` into a temp file, re-apply
    your own edits to THAT, hash THAT. Never `git hash-object` a working copy you
    read earlier. Better still, make your push helper REFUSE when a named path moved
    between your blob's base and the tip — that is a check the next lane inherits
    instead of a paragraph it has to remember.
    ⚠ **AND AN ALLOCATED ID IS A BLOB TOO (DEF-1787, 2026-08-27).** The same
    re-derivation covers the numbers you took out of a shared register, and for the
    same reason: `file_defect.py` reads the working tree, `HEAD`, `@{upstream}` and
    every `refs/remotes/origin` ref — **all of which are the PUSHED world plus your
    own checkout.** A sibling working in its own clone or worktree has rows in NONE
    of them until it pushes, so two lanes correctly compute `max + 1` and correctly
    get the SAME number. It happened on 2026-08-27: two lanes both took `DEF-1783`
    and `DEF-1784`, minutes apart, and the allocator's printed line was accurate
    both times. **Nothing downstream would have caught it** — a duplicate id in a
    957-row register reads as a register, not as an error.
    **So at push time, re-derive BOTH: the file content AND the ids.** Re-resolve the
    tip, re-read the register from it, and confirm every id you allocated is still
    free; if it is not, renumber before you commit. It is the same command and the
    same moment as the blob check above — treat them as one act, because they are.
    ⚠ **AND THE RE-DERIVATION MUST BE UNCONDITIONAL — PUTTING IT INSIDE CONFLICT
    HANDLING IS WHERE IT STOPS RUNNING (2026-09-05, self-reported).** A lane's
    land script re-derived the next free number from the pinned tip correctly, and
    put that step inside the branch that resolves a CONFLICT on the register. On
    the run that actually pushed, git merged the register **cleanly**, so the
    branch never ran and two rows kept numbers allocated three tips earlier; two
    other ids had landed in between and the register published duplicates.
    **Whether two lanes touched the same LINES of a register has nothing to do
    with whether they took the same NUMBER out of it** — an append-only file
    merges cleanly almost every time, so the clean path is both the common case
    and the dangerous one. The clause above says re-derive at push time; this says
    it is one unconditional step on every push, never a branch of anything.
    ⚠ **AND IT IS NOT ONLY DEFECT IDS — THREE FAMILIES COLLIDED IN ONE AFTERNOON
    (2026-09-04).** A defect id (`DEF-1787`), a **gate number** (`DEF-CWP-3734` —
    THREE lanes, three correct computations of "the next free number", one
    answer), and a **version** (`DEF-GOV-3756` — two lanes both shipped
    `2.141.0`). Every lane's arithmetic was right; what was wrong was *which
    world the maximum came from*, because a sibling in its own worktree has its
    rows in NONE of the places a listing can see until it pushes.
    **`10-scripts/allocate.py` asks the remote instead of this checkout:**
    `allocate.py defect` · `allocate.py gate` · `allocate.py version --bump
    change`, and — the one that matters — `allocate.py <family> --verify <N>`,
    which exits 1 if the number was taken while you worked. Run the verify in
    the same breath as the blob re-derivation. ⚠ **It CANNOT reserve and does
    not claim to:** nothing writes to the remote, so two lanes calling it in the
    same second still collide. It removes the STALE read, which is the common
    case, and catches the rare one at the only moment the answer can be final.


    ⚠ **AND EVERY CHECK ABOVE MEASURES AGAINST THE TIP, WHICH IS THE ONE
    BASELINE YOUR OWN EARLIER WORK IS ABSENT FROM (DEF-CWP-3771, 2026-09-04 —
    A LANE DELETED ITS OWN FUNCTION AND SELF-REPORTED IT).** The re-derivation
    this law prescribes rebuilds a file as **the pinned tip plus your own
    hunks**, and "your own hunks" is whatever the author has in front of them —
    which is the change they are making now, not the one they appended to the
    same file forty minutes earlier and already committed. So the second edit
    lands and **the first is subtracted**, silently.
    **It defeats the whole law, and each check is true when it passes:**
    `git diff --numstat <tip> <commit>` reports ZERO deletions — correctly, the
    tip never held the earlier function; `git show <commit>` shows only your
    own hunks — correctly; the file count is right; lint passes; and the suite
    you ran does not import the path you just removed. On 2026-09-04
    `level_pay_position` vanished from `billing_seam.py` while `selectors.py`
    went on calling it, and `GET /portal/level-pay` would have raised
    `AttributeError` on the branch.
    **The missing comparison is against YOUR OWN PREVIOUS COMMIT, not the tip:**
    `git diff --numstat <your last commit on this file> <the rebased one>` —
    deletions there are yours being erased by yourself. Run it whenever you
    re-derive a file you have ALREADY committed to in this session, which is
    exactly when the tip stops being a safe baseline for your own work.
    **The general form, and it is worth more than the command:** every check in
    this law protects you from SIBLINGS. None of them protects you from your
    own earlier self, because the tip — the thing they all measure against — is
    defined as *the world without your uncommitted work in it*, and your
    committed-but-unpushed work is in exactly that blind spot.

    ⚠ **AND A TOOL THAT LOOKS LIKE AN APPEND IS A WHOLE-FILE WRITE — WHICH DOES
    NOT FAIL THE CHECKS ABOVE, IT DISABLES THEM (TWICE ON 2026-09-06, BY TWO
    LANES THAT HAD BOTH READ THIS LAW).** Adding or editing one row of a shared
    register through Python's `csv` writer **re-serialises EVERY row**: quoting
    and line endings are the writer's own choices, so a 1,900-row register comes
    back with every line changed on disk even where its content did not move.
    **No data is lost — and that is what makes it dangerous**, because every
    check this law prescribes comes back clean. The file count is right. Your
    own row IS present. `git diff --numstat` shows insertions and deletions in
    equal number, exactly as a rewrite should. And `git show <commit>` shows
    **1,967 hunks**, so *"read the hunks and confirm every one is yours"* — the
    check DEF-182 added precisely to catch this class — **cannot be performed at
    all.** A check you are unable to run is worse than one that fails.
    **What it costs when it goes wrong:** a copy read minutes earlier silently
    reverts a row a sibling has since pushed (mechanism two), and a pathspec
    commit naming only the register **publishes every other lane's in-flight
    row** with it (DEF-168, mechanism five). Both are invisible inside a
    whole-file diff.
    **So: never round-trip a shared register. Use the tool that owns the file** —
    `10-scripts/file_defect.py` appends ONE row as raw bytes and refuses to edit;
    `close_defect.py` rewrites ONE line's bytes and splices it between two byte
    slices it never parsed; `merge_register.py` resolves an append/append
    conflict and refuses when both sides took the same id. Each exists because
    this already happened, and each says so in its own docstring.
    **If you must do it by hand, append rather than rewrite** — `cat <the tip's
    file> <your raw row> > new` — and **prove the prefix**:
    `diff <(head -c $(wc -c < tip) new) tip` must be empty. A register whose
    first N bytes are byte-identical to the tip cannot have reverted anybody.
    ⚠ **THE REASON THIS IS A LAW AND NOT A TIP: BOTH LANES WERE BEING CAREFUL.**
    One re-derived from a pinned tip and verified field-by-field that only its
    intended row had changed — true, and it still shipped a 1,967-line diff. The
    other was appending, which is the safe operation, through an unsafe tool.
    **Reaching for a serialiser is the obvious move and it is always wrong here;
    the habit that saves you is to look for the tool that owns the file before
    writing to any register.**
    ⚠ **AND THAT LAST HABIT IS THE GENERAL LAW, NOT A REGISTER FOOTNOTE — THE SAME
    ROOT CAUSE BIT A THIRD TIME THE SAME NIGHT, ON A DIFFERENT FILE.** A lane that
    had reverted eleven of a sibling's stamps did the right thing afterwards: it
    wrote a push helper that refuses when a named path moved under it, proved its
    first guard could never fire, rewrote it, and watched it refuse before
    trusting it. All correct — **and `10-scripts/push_paths.sh` had been in the
    repo since `CR-056`, implemented exactly that refusal, and was STRICTER**: it
    also refuses a base that IS the tip (`DEF-GOV-4061`, because then the
    staleness check compares the tip with itself, cannot fire, and prints a line
    that reads exactly like a pass — law 7's *incapable of failing* shape), and
    it refuses a line VANISHING from a shared register (`DEF-2837`). It was on
    the branch at the commit that lane started from. **So the cause of the revert
    was not a missing guard; it was an existing guard nobody looked for**, and
    the fix is `ls 10-scripts/` before writing a helper, not another helper.
    **Three occurrences in one night, three different files, one cause: a
    careful operator reached for the obvious general-purpose tool — a `csv`
    writer, a hand-rolled push script — instead of asking whether this repo
    already owns that job.** Every one of them had read this law. **So before
    you write ANYTHING that touches a shared file, read `10-scripts/`'s listing
    first.** The tools there exist because the damage already happened once, and
    each says so in its own docstring — which is the uncomfortable part: the
    knowledge was written down three times and none of it was where a lane looks.
    ⚠ **AND `push_paths.sh` REFUSED THE VERY COMMIT THAT ADDED THIS PARAGRAPH**,
    on the base-is-the-tip check, because the tip had moved while it was being
    written. That is the guard working on its author, which is the only kind of
    proof worth having.

    **A stale index is a loaded gun:** if you find one holding a revert, the working
    tree is the truth — confirm `git diff HEAD` is empty, then `git reset` to disarm it.
    ⚠ **AND THE PROCEDURE ABOVE IS HOW YOU LOAD IT (DEF-613, twice in one session).**
    `export GIT_INDEX_FILE=…` stays set for the REST of that shell invocation, so an
    ordinary git command after it — `git reset --mixed <sha>` to sync the local ref, say —
    writes to the PRIVATE index and leaves `.git/index` at its pre-lane state. `git status`
    then reports **`D` for every file the lane just created and pushed**, and a bare
    `git commit` would commit the deletion of work that was live on the branch a minute
    earlier. **So: run the commit-tree procedure in its OWN shell invocation, or prefix the
    variable per command (`GIT_INDEX_FILE=… git write-tree`) instead of exporting it.**
    **And `git status` after every commit-tree push, before declaring done** — all the
    post-push checks in this law read COMMITS (`git show`, `git diff --numstat`,
    `git show HEAD:<path>`), every one of them passed, and the tree was wrong anyway.
    ⚠ **AND A CLEAN `git status` IS THE SYMPTOM, NOT THE CHECK — THE COMMIT-TREE
    PUSH LEAVES YOUR WHOLE TREE STALE AND `git reset --mixed` DOES NOT FIX IT
    (DEF-2474, 2026-08-30).** `commit-tree` builds from the PINNED TIP, never from
    your working tree — which is exactly why it is safe — and it therefore updates
    **no file on disk**. Sync the local ref afterwards with `git reset --mixed <sha>`
    and you have moved HEAD and the index past every commit siblings pushed while
    leaving all their files at the content you started with. **`git status` then
    reports CLEAN, because the index matches the tree it was just told to match.**
    The tree is now a loaded revert of every file those commits touched, and the
    next ordinary pathspec commit in it publishes that revert **with a correct file
    count**. On 2026-08-30 that was **39 files** — a 77-line deletion of
    `components/icons.tsx`, all eleven locale catalogues and 443 lines of
    `TemplateCatalog.tsx` — sitting under two live lanes.
    **Every check in this law passes on it**, and for a reason worth naming: they
    all read COMMITS, and the commit is fine. The damage is not in what you pushed,
    it is in what you LEFT BEHIND.
    **So after a commit-tree push, move the FILES too**: `git merge --ff-only
    origin/<branch>` — the form that refuses rather than discards — or, if you must
    reset, write the tip's bytes over every path that differs afterwards
    (`git show "$TIP":<path> > <path>`, which also recreates files the sync
    deleted, then re-set modes from `git ls-tree "$TIP"`).
    **And verify by SUBTRACTION, not by status: `git diff --numstat "$TIP"` must
    print NOTHING.** A clean `git status` cannot tell you this and never could.
    ⚠ **A SECOND NEAR-MISS IN THE SAME HOUR, AND IT IS A TRAP IN THE REPAIR ITSELF.**
    The script written to apply the paragraph above did `open(dst,"w")` and only
    then read its input — **so when the read failed, the output file had ALREADY
    been truncated**, and the `cp` that followed copied zero bytes over `CLAUDE.md`.
    This law survived because `git diff --numstat "$TIP" <commit>` printed
    `0 519 CLAUDE.md` and the commit was never pushed. **Build the new content in
    full, assert it is non-empty and longer than what it replaces, and only then
    write over anything** — and never let a re-derivation script open its
    destination before it has the bytes to put in it.
    ⚠ **AND THE FIFTH OCCURRENCE WAS THE MIRROR IMAGE (DEF-168, same day again).**
    A pathspec commit takes the whole file, so as well as REVERTING another lane's
    change it can **PUBLISH one** — a lane committed `rating/services.py` for its own
    hunks and shipped another lane's new `seed_sample_records(actor)` while that
    lane's matching caller was still uncommitted. Red for two commits on
    `TypeError: seed_sample_records() missing 1 required positional argument`.
    **Both checks above pass on it:** the file count was right, and the author's own
    change *was* in HEAD. Neither asks about the **extra** content the commit carried.
    **So the post-push check is `git show <commit>` — READ THE DIFF, and confirm every
    hunk is yours**, not merely that yours is present.
    ⚠ **`--stat` IS NOT ENOUGH, AND THIS RULE HAS NOW BEEN WRONG TWICE (DEF-182).**
    `--stat` lists file NAMES and line counts, so it can tell you *which* files a
    commit touched and can NEVER answer *"is every change inside them mine"* — which
    is the only question this check exists to ask. A lane ran it exactly as written,
    it passed, and its commit had published another lane's uncommitted rows in a
    shared register. Nothing was lost, and the check reported success over the thing
    it was pointed at. **Read the hunks. On a big commit, `git show <commit> -- <the
    shared files>` narrows it without weakening it.**
    **Both times this clause was wrong, a lane following it correctly is what found
    the flaw** — first `git diff HEAD~` comparing the working tree (DEF-174), now
    `--stat` reading only names. A check whose output cannot distinguish pass from
    fail is worse than no check, because it is trusted. ⚠ **NAME THE COMMIT. Do NOT write a
    bare `git diff HEAD~` (DEF-174):** without a pathspec that compares the WORKING
    TREE to a commit, so in a shared tree it prints four other lanes' in-flight work
    as though it were yours. It reported *1 insertion, 1550 deletions* for a commit
    that had touched three files for +6/-2 — and the false alarm led straight to a
    `git checkout HEAD~ --` over six shared files, the forbidden command again, at
    speed, on evidence that was wrong. **Verify before you remediate, and remediate
    non-destructively:** `git show <commit>:<path>` proves what a commit holds
    without touching anything, and the "deleted" file was byte-identical in both. Three mechanisms, one cause:
    in a shared tree a commit is a statement about FILES, and you only ever author
    HUNKS.
    ⚠ **SIXTH AND SEVENTH, AND THE SEVENTH IS WHY THE BAN ABOVE IS WORDED WRONG
    (DEF-172).** A lane ran `git stash` — explicitly forbidden three lines up — and
    reverted five other lanes' unsaved work for ninety seconds. It self-reported, and
    its diagnosis is the useful part: **the ban reads as being about stashing YOUR
    work, and the dangerous use is a throwaway diagnostic** — *"let me stash to see
    what the tree looks like clean"* — where the stashing is incidental to the intent
    and the rule never comes to mind. So read it this way instead: **any command that
    makes the working tree momentarily not-what-it-was is forbidden**, whatever you
    wanted it for, because for those seconds five other lanes are reading a tree you
    silently emptied. That covers `git stash`, `git checkout -- <path>`, `git
    restore`, `git reset --hard` and `git clean`. **To look at a clean tree, look at
    HEAD** — `git show HEAD:<path>` — or use a `git worktree`. Never move the shared
    one. **And if you do it anyway: restore immediately and verify FILE BY FILE, then
    file it.** That lane did, which is why nothing was lost.
    **The seventh, for completeness:** an unsaved surface-debt sentence was swept up
    by another lane's commit before its author committed it — mechanism two again.
    **Which is the practical rule underneath all seven: commit small and commit
    often.** Work you have not committed is work any of six other lanes can erase,
    and a container restart the same day destroyed six lanes' uncommitted work
    outright. A partial fix on the branch beats a complete one in a dead container.

12. **RUN `./10-scripts/check_head_current.sh` AS THE FIRST COMMAND OF EVERY
    SESSION, AND AGAIN AFTER ANY GAP — BEFORE YOU READ A FILE OR BELIEVE A GREP
    (DEF-351, and FIVE MORE ON 2026-08-25).**
    Local HEAD silently rewinds. On 2026-08-20 it went back 240 commits; on
    2026-08-25 it went back to the *same* previous-day commit **five times**,
    the worst losing **152 commits** from the working tree.
    **The reflog is the diagnosis and it is unambiguous:** after a rewind there
    is **no reflog entry for any of the session's commits** and `HEAD@{1}` is
    the previous day's. A `git reset` would leave an entry. So those commits
    were never made in the `.git` that is present afterwards — **the container's
    filesystem, `.git` included, is restored from a session-start snapshot, and
    ONLY WHAT WAS PUSHED SURVIVES.** No repo change can prevent this. It is the
    environment, not a bug you can fix.
    ⚠ **AND IT DEFEATS EVERY CHECK IN LAW 11 ABOVE, WHICH IS WHY IT NEEDS ITS
    OWN RULE.** Law 11's checks all ask *what does this commit contain* — the
    file count, the hunks, re-reading each file from HEAD, `git diff --numstat`
    against the tip. **Every one of them assumes HEAD is where you left it.** A
    rewind moves the POINTER and touches no file, so `git status` is clean, no
    command fails, the tree looks healthy, and all of those checks pass over a
    tree that is 152 commits stale. DEF-351 surfaced only because a directory
    listing for an unrelated reason ended at `g27` where it should have ended at
    `g37`.
    **The failure mode is a WRONG CONCLUSION, not lost work.** A file that "does
    not exist" may simply not exist *yet*; a rule that "was never written" may be
    written and pushed. On 2026-08-25 a status report was assembled from a tree
    missing a day of work, and only the check caught it.
    **Recovery, when the tree is clean:** `git merge --ff-only origin/<branch>` —
    the form that refuses rather than discards — then `(cd 07-frontend && npm ci)`,
    because a rewind past a dependency change silently reinstalls the OLD set and
    turns healthy tests red. **If the tree is NOT clean, someone is mid-edit:
    leave it and say so.**
    ⚠ **AND "LEAVE IT AND SAY SO" IS WRONG — IT PRESERVES THE DAMAGE
    (DEF-2100, 2026-08-28).** After a rewind the tree is not clean OR dirty; it is
    a **MIX**, and the two halves need opposite treatment. On 2026-08-28 HEAD was
    276 commits behind with 166 files differing from the tip: **117 of them nobody
    had touched, so they still held PRE-TIP content — a revert of up to 276 pushed
    commits, sitting under two running lanes** — and 49 were live lane edits that
    must not be moved. `06-backend/apps/billing/resolution_shadow.py`, 712 lines
    and put on `human_owned.txt` by PO ruling that same morning, was simply ABSENT
    from the tree. Following the clause above literally would have left all 117
    loaded for the rest of the session, and **law 11's checks cannot see it**: a
    lane committing one of them has the right file count, its own hunks present,
    and a diff that never mentions the work it erases.
    **Separate the two halves before deciding — it is two commands.**
    `git diff --name-only <tip>` is everything wrong; `git diff --name-only HEAD`
    is what a lane has touched since the rewind. **The set difference is the stale
    half, and that half is safe to restore precisely because nobody has touched
    it.** Restore it by WRITING the tip's bytes — `git show <tip>:<path> > <path>`,
    which also recreates files the rewind deleted — never with `git checkout`,
    which law 11 bans and which would take the live half with it. Then
    `git reset --mixed <tip>`, which moves HEAD and the index and touches **no
    file**, so `git status` stops lying. Two things to verify afterwards, both
    learned the hard way the same day: compare byte-for-byte against the tip (a
    file created *after* the stale HEAD is untracked, so `git diff` keeps calling
    it deleted even once its bytes are correct — **the diff is not the check**),
    and re-set each file's MODE from `git ls-tree <tip>`, because a plain write
    drops the executable bit and a mode-only difference is invisible to every
    check that reads content.
    ⚠ **AND THAT MODE TRAP IS REACHABLE FROM THIS RECOVERY ITSELF, NOT ONLY FROM
    A REWIND (2026-09-04, CR-068 wave E).** Read the clause above again: the
    command it PRESCRIBES for restoring a stale file is
    `git show <tip>:<path> > <path>` — and a shell redirect creates the file with
    the default mode, so **it drops the executable bit every single time it
    restores a `100755` file.** The procedure the law recommends therefore
    manufactures the defect the law warns about, on every script it touches, and
    nothing downstream can see it: the bytes are perfect, so a byte-for-byte
    comparison passes, `git diff --numstat` prints nothing, and a content check
    of any kind is looking at the wrong thing. **`git status` is the only place
    it shows, as a bare `M` with a zero-line diff** — `old mode 100755 / new mode
    100644` and not one line of content.
    On 2026-09-04 a lane syncing its own worktree turned `10-scripts/allocate.py`
    non-executable this way, and the next pathspec commit naming that file would
    have published *"the allocator is no longer executable"* with a correct file
    count, correct hunks and nothing in the diff to notice.
    **So the mode restore is not a step you do AFTERWARDS to the files you
    remember — it belongs in the same loop as the write, keyed off
    `git ls-tree <tip>` for every path, every time.** A restore helper that
    writes bytes and does not `chmod` is half a restore, and it is the half that
    leaves no trace.
    **Then tell the running lanes the tip SHA**, because the half you did not touch
    is still being edited on a stale base — on 2026-08-28, 47 of those 49 files
    were, the shared registers and this file among them.
    ⚠ **AND THE SET DIFFERENCE ABOVE IS NOT ENOUGH — IT MISSED 35 FILES, EVERY
    SHARED REGISTER AMONG THEM (DEF-2100, corrected the same hour it was
    written).** The difference of the two `--name-only` sets only finds files
    matching the stale HEAD *exactly*. A rewind can leave a file at some
    **intermediate** version — not the tip, not the stale HEAD — and that file
    lands in the "live, do not touch" half and keeps its revert. On 2026-08-28
    the first pass cleared 117 and left 49; **35 of those 49 were pure staleness
    too**, including `12-governance/02-decision-log.md`, `01-open-questions.md`,
    `09-human-review-ledger.md`, `11-change-requests.md`, `14-id-reservations.md`,
    `CLAUDE.md`, `CHANGELOG.md` and `06-backend/apps/customers/api.py`, which held
    the pre-`DEF-1702` form with the list filters deleted.
    **The test that actually decides it is content-addressed, and it is
    conclusive: is this file's exact blob an OLDER version of this same path?**
    `git hash-object <path>`, then walk `git log --format=%H -- <path>` and
    compare `git rev-parse <commit>:<path>`. A hit proves no lane authored the
    content — it is a version this repo already had — so it is safe to restore.
    A miss is not proof of the opposite, only absence of proof, so **leave a miss
    alone**: it is either real in-flight work or a partially-edited stale file,
    and its owner is the one who can tell. Run it over every file still differing
    from the tip after the first pass, and expect the walk to be depth-limited on
    a high-churn path like the defect register, which is another reason a miss
    decides nothing.
    **Then confirm the survivors are SUPERSETS, not reverts** —
    `diff <(git show <tip>:<path>) <path>` must show additions only. That one
    command is what separates a lane legitimately writing on the tip from a lane
    writing on a stale base, and it is the check to re-run after telling the lanes
    the tip SHA.
    **And a revert verdict means RESTORE it, not leave it.** On 2026-08-28 the
    content-addressed test left 15 files unproven and the superset check settled
    every one of them: **ALL FIFTEEN WERE REVERTS** — all thirteen locale files,
    `07-frontend/src/api/endpoints.ts`, `ImportWorkflowPage.tsx`, and
    `12-governance/10-defect-log.csv` **missing 992 lines of the tip**. There was
    never any live work in that tree at all: both lanes had worked in private
    `git worktree`s, which is why they lost nothing and why the shared tree was
    stale end to end. **So the honest default after a rewind is that the WHOLE
    shared tree is stale until a file proves otherwise**, and the thing that
    proves otherwise is a lane saying "that one is mine" or a superset diff — not
    the fact that a file merely differs from the stale HEAD.
    ⚠ **AND THE RESTORE ABOVE IS ONLY HALF A SYNC — IT WRITES AND IT NEVER
    DELETES (DEF-2872, 2026-09-01).** Every sentence of this recovery is about
    CONTENT: the tip's bytes, a superset diff, a file the rewind removed. **The
    mirror case is a file the TREE HAS and the TIP DOES NOT**, and it arrives
    from an ordinary sibling action rather than from a rewind: a lane pushes
    `customers/migrations/0038_cr056_w6_company_tax_id.py`, a later lane renames
    it, and any tree that synced in between now holds BOTH spellings. Django
    then refuses **every test in the process** with *"Conflicting migrations
    detected; multiple leaf nodes in the migration graph"* — which is not a test
    failure, names neither lane, and looks for all the world like the tree is
    broken.
    **Every check in laws 11 and 12 passes on it**, and for the reason DEF-2100
    already recorded once: the leftover is UNTRACKED, so `git status` is clean
    for it and `git diff --numstat <tip>` says nothing about it either. The
    damage is once again in what was LEFT BEHIND rather than in what was pushed.
    **So the sync has a delete half, gated on the same content-addressed test
    this law already prescribes in the other direction:** for every path present
    in the tree and absent from the tip, `git hash-object` it and walk
    `git log --format=%H -- <path>`. **A HIT proves the blob is a version this
    repo already had** — no lane authored it here — so it is safe to remove. **A
    MISS decides nothing and the file is LEFT ALONE**: it is either real
    in-flight work or a partially-edited stale file, and only its owner can say.
    **A tree is synced when it matches the tip in BOTH directions**; a helper
    that only writes is only half a sync.
    **Which is also the cheapest lesson here: dispatch every lane into its own
    `git worktree`.** Two lanes did on 2026-08-28 and a rewind that reverted 152
    files of the shared tree cost them nothing.
    **The other half of the mitigation is rule 11's last line, and it is the half
    that actually saves you: PUSH after every step, not at the end.** Nothing was
    lost across six rewinds in one day, and the only reason is that every piece of
    work had been pushed within minutes of being made. **A push is the sole
    durable act in this environment** — a commit alone is not.

13. **NEVER ASK THE PO THE SAME THING TWICE. THE REPO IS WHERE AN ANSWER LIVES —
    ASKING AGAIN IS A BUG IN US, NOT A CLARIFICATION (PO ruling 2026-08-27).**
    Verbatim, and it was said twice in one hour: *"all these ruling please mark in repo
    and dont ask again and again"* — then, after a re-ask: *"this is very exzuating and
    taxing as a human. Icant keep consistency if you keep asking - i try to be
    consisitence but as human i might make a mistake in my response - hence it is
    improtant you note it nore when I say so and dont ask again and again"*.
    **READ THE SECOND ONE AGAIN, BECAUSE IT NAMES A FAILURE MODE AND NOT A PREFERENCE.**
    A person answering the same question twice from memory will eventually answer it
    DIFFERENTLY — and then the repo holds two rulings that contradict each other, both
    genuine, with no way to tell which is current. **So a re-ask does not merely cost the
    PO time: it manufactures inconsistency and then blames the human for it.** The PO
    said as much before we noticed it ourselves.
    **THE RULE: before putting anything to the PO, grep `12-governance/02-decision-log.md`
    and `01-open-questions.md` for the subject.** If it was ruled, it is ruled — build it.
    This costs one command and it is not optional; on 2026-08-27 the merge lane put
    *"premises owner = master account"* back to the PO having recorded that exact ruling
    itself six hours earlier.
    **WHAT LEGITIMATELY REACHES THE PO, and it is a short list:**
      * a ruling that **collides with a signed rule** — the supersession must be stated,
        never assumed;
      * a **❄️ FROZEN B4/B5 figure**, which cannot move without a re-sign (a constraint on
        us, not a question we chose to ask);
      * a fact **only they hold** — a tax authority's requirement, a price, a deadline.
    **EVERYTHING ELSE IS OURS TO DECIDE AND WRITE DOWN.** A judgment call recorded in the
    decision log with its reasoning is the deliverable; a question is the failure to make
    one. And when a ruling arrives, WRITE IT DOWN THE SAME TURN — law 9 already says this,
    and this law is what it costs when we do not.
    ⚠ **A ruling that arrives in a form we did not expect is still a ruling.** *"this si
    corerct"*, *"okay dont link it"*, *"a for now, c if it bites"* are all complete
    answers. Asking for a tidier restatement of a decision already made is the same bug
    wearing better manners.

14. **A FAILED STATEMENT POISONS THE WHOLE POSTGRES TRANSACTION, AND THE TEST SUITE
    RUNS ON SQLITE, WHICH DOES NOT — SO THE NAIVE FIX PASSES EVERYTHING AND LOSES
    PRODUCTION DATA (found INDEPENDENTLY by two lanes on 2026-08-29).**
    `try: … except IntegrityError: continue` is the obvious way to skip a bad row
    and carry on. **On PostgreSQL it does not work.** Once any statement errors
    inside a transaction, the transaction is aborted; every later query raises
    `InFailedSqlTransaction` and the work is lost at COMMIT anyway. **A SAVEPOINT
    — a nested `transaction.atomic()` — is not the tidy option, it is the ONLY
    option**, and the code comment should say so or the next lane will "simplify"
    it away.
    ⚠ **THE REASON THIS IS A LAW AND NOT A TIP: `config/settings/test.py`
    HARDCODES IN-MEMORY SQLITE AND IGNORES `DATABASE_URL`** (the URL applies only
    under `DJANGO_SETTINGS_MODULE=config.settings.local`). **SQLite has no aborted-
    transaction state.** So the broken version passes the entire suite, green, on
    every machine, and fails the first time a real row is refused in production.
    Both lanes found it only by re-running the transaction-sensitive cases against
    a real PostgreSQL and watching them break:
        `django.db.transaction.TransactionManagementError: An error occurred in
         the current transaction. You can't execute queries until the end of the
         'atomic' block.`
        `psycopg.errors.InFailedSqlTransaction: current transaction is aborted,
         commands ignored until end of transaction block`
    **So: any code that catches a database error and continues MUST be proved on
    PostgreSQL, not on the default suite.** One lane was skipping import rows, the
    other was queueing a payment receipt — different modules, different weeks of
    work, same trap, neither aware of the other.
    ⚠ **AND READING THE ERROR CODE TAKES A WALK, NOT ONE HOP.** `exc.__cause__` on
    a caught Django `IntegrityError` is *another* Django `IntegrityError`; the
    driver's exception with the real SQLSTATE is two or three hops down. A first
    draft that read one hop returned the generic sentence for every row and
    **looked handled** — the same class as a check that cannot fail.
    **Cheapest mitigation, and it is free:** run these suites with
    `JOBS_EAGER=false --reuse-db`. `JOBS_EAGER` defaults to true under the local
    settings and seeds a whole sample utility per fixture — one lane measured a
    twelve-file run at an hour that took four minutes with it off (DEF-567).
    ⚠ **AND `--reuse-db` DID NOTHING AT ALL UNTIL 2026-09-04 (DEF-GOV-3778).**
    Django's SQLite backend builds its test database **in memory unless
    `TEST["NAME"]` is set**, and `config/settings/test.py` set only `NAME`. So
    every run by every lane re-applied all 278 migrations: **133 seconds of
    fixed cost per `pytest` invocation**, invisible because the flag is ignored
    rather than refused — no warning, no error, and identical output whether
    the reuse works or cannot. It is fixed (the test database is now a file
    named for a digest of the migrations, so it rebuilds itself when they
    change): **133s → 9s on one file, 12m30s → 6m15s on the whole portal
    suite.** The lesson generalises past this bug — **a flag that is silently
    ignored is worse than one that errors, and the only thing that finds one is
    measuring the wall clock you had stopped noticing.**

**Defect register:** `12-governance/10-defect-log.csv` (+ `10-scripts/defect_report.py`).
Add a row for every defect the PO reports. Its `escape_reason` column — why no
existing check caught it — is what turns a bug list into a process fix.
