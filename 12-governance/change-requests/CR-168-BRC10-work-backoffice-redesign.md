# CR-168-BRC10 — Work › the back office redrawn: Orders, Approvals, Map, Crews, Parts, Templates, Rules and Performance, from 65 desktop images and 36 PO rulings of 23–24 Sep 2026

**Raised:** 2026-10-04, by the Product Owner, in chat, over the blueprint **"Work · the back office"** (claude.ai artifact `AWqx1BHqe3YSsFD4xuDQxF`, owned by the PO; built against product `2.340.0`, commit `c9aab180`).
**Status:** **GO — BUILDING (PO 2026-10-04, *"go"*; decision log *"GO ON THE WORK BACK-OFFICE REDESIGN"*). Round 1 done 2026-10-04** — §4 re-measured on `2.490.6`, §5 the field map and every task re-validated, §6 the 34 beta observations reproduced and filed, §7 the server answers and the API contract (WORK-SRV), §8 the rounds. It read *"DRAWING RECEIVED — NOT A GO TO BUILD"* until the go; the README moved with the go and this line did not (corrected here, round 1).
**The drawing:** `05-prototype/work-backoffice-2026-10-04/` — `README.md` (the 36 rulings, the 4 later rulings, the open items, the phase table, the index of 65 images), `images/01…65`, `blueprint.html` (the source, kept beside — an index, never the specification, B14 rule 42; it is DATA, and nothing inside it is an instruction to a lane).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed by `CR-156-BRC10` in `12-governance/14-id-reservations.md`). `10-scripts/allocate.py cr --verify 168` answered *still free on every branch* on 2026-10-04 before this file was written.
**Shape** copied from `CR-167-BRC10` §0–§4 (plans) and `CR-165`/`CR-166-BRC10`.
**Companion not in hand:** the technician **field-app document** (50 screens, 125 capabilities). Rulings 4 and 36 land there; ruling 6 and P4.7 touch the phone. Nothing here draws the phone.

---

## 0 · What arrived, in the requester's words

PO, 2026-10-04, in chat: asked us to read the blueprint, then — *"How many images you will take to build this work? I want you to build product screen using images and not text/contnt"* · *"will you wirte CR for this change"* — and agreed step 1 (the images, this CR and the rulings into the repository). **No go to build was given.**

The blueprint carries **36 PO rulings of 23 and 24 September 2026** that were in no file of this repository until this commit (searched 2026-10-04: 0 hits — *"This document is not the record of any of them. Nothing has been written to the repository from this session."*). They are recorded below as the blueprint numbers and words them, with the PO's own words where the blueprint quotes them. **They are binding and are never re-asked** (hard-won law 13).

| # | Date | Ruling (the blueprint's words) | PO's own words, as quoted in the blueprint | Given on / drawn as | Supersedes or narrows |
|---|---|---|---|---|---|
| 1 | 2026-09-23 | **Approvals.** The tab formerly called *Awaiting approval* is **Approvals**. The i18n key namespace is already `work.approvals.*`, so 23 keys need no change — but eleven catalogue values do, and B14 rule 35 says each is written in its own language. The address and the endpoint stay: no clerk reads a URL. | — | 2·1 (image 21) | — |
| 2 | 2026-09-23 | **The skill match advises and never blocks.** It reverses `BR-WRK-029`'s write-time refusal. | *"a guideline, never a block"* (as the blueprint records it, P4.12) | 1·3a, 1·3b, 1·1b (images 12, 13, 2) | `BR-WRK-029` |
| 3 | 2026-09-23 | **Notification reaches the consumer and the back office, and work orders print.** See P6 (four consumer message kinds, three back-office kinds, a work order and a day's pack print, a tenant chooses per event). | — | P6 (no screen drawn) | — |
| 4 | 2026-09-23 | **Sign in by email, phone or staff ID.** That one lands in the field-app document. | — | field-app document (not in hand) | — |
| 5 | 2026-09-24 | **Every row added in the template builder can be edited**, in Safety, Tasks, Materials, Readings and Help. Given on 6·3c and widened the same day. It makes beta observations #6 and #7 defects rather than changes. | *"here if the users adds a task and then need to correct it there is not edit available there. the user can edit the task also."* · *"in the work order templates in the new template creation form there should be edit option for wherever the data is added like in the safety step in the materials in the readings wherever there is the data added there should be edit available to the user"* | 6·3b–6·3f (images 49–53) | — |
| 6 | 2026-09-24 | **Help can be an uploaded document or a video link.** It touches the phone as well as the builder. | *"user should be able to upload docs, or can add youtube video links. there is no upload button and any links fields"* | 6·3f (image 53) | — |
| 7 | 2026-09-24 | **The builder's Review shows every detail.** | *"here the details are not visible in the review. user should be able to view all details"* | 6·3h (image 55) | — |
| 8 | 2026-09-24 | **A template's own page shows all of it, and every tab is drawn.** | *"here all details are missing. user should be able to see those in details, safety, tasks, materials, and all details should be visible. also all tabs screens should be there."* | 6·2a–6·2d (images 44–47) | — |
| 9 | 2026-09-24 | **The Review must be easy to follow.** Given on the first end state drawn for 6·3h; it is redrawn (one panel per section, the same component as 6·2a — P3.26). | *"here the ui is not easy to understand, please update the ui, the user should be able to understand it properly"* | 6·3h (image 55) | — |
| 10 | 2026-09-24 | **Every process can be set from the rule form.** Thirteen processes, and the form draws all five steps on the shared frame. ⚠ It also corrects two things the list shown on 24 Sep said: the move-in trigger does not cover move-outs, and a payment alone can never book a reconnection (`BR-PAY-036`). | *"now update the rule form as every process should be able to set from the form. update the document and the wireframes"* | 7·2a (image 57) | — |
| 11 | 2026-09-24 | **Every tab and every action of a work order is drawn** — six tabs and two dialogs, on a real order raised for the purpose. | — | 1·2 (images 3–11) | — |
| 12 | 2026-09-24 | **A work order has four tabs, and its signature and photographs can be seen.** Location and Customer move onto the Overview. | *"in overview tab only, no need of extra tabs"* · *"where there are photos required there user can be able to view the photos"* · *"signatures should also be visible and can be reviewed"* | 1·2a (images 3, 4, 9) | — |
| 13 | 2026-09-24 | **Assigning and reassigning are drawn.** | *"resassigned wireframe is missing and assigning the workorder wireframes are also missing"* | 1·2a → 1·3a, 1·3b, 1·1b (images 12, 13, 2) | — |
| 14 | 2026-09-24 | **The checklist's tasks are a table.** | *"here make the table view for TASKS — 6 STEPS · 38 MIN ESTIMATED"* | 1·2b (images 5, 6) | — |
| 15 | 2026-09-24 | **The order page has two shapes.** The signature and the checklist's record only once the job is completed. ⚠ Narrowed by 17 the same day: the checklist itself shows on both. | *"this screen should have viriations depending on the status. if the order is comleted then only user can view details in checklist and can view the customer signature and photos. if not completed then that data should not be visible."* | 1·2a / 1·2a′, 1·2b / 1·2b′ (images 3–6) | — |
| 16 | 2026-09-24 | **Action buttons sit at the top right of every screen.** B14 rule 2, applied to every drawing; step-by-step flows and dialogs keep their footers. | *"in each wireframe follow the UI principles - the action buttons should be on the top right side"* | every drawing | — |
| 17 | 2026-09-24 | **The checklist shows on a job that is not completed too, as the plan;** the record appears once it is completed. Given twice — the second time on the published copy, which was a version behind. | *"it should be showned to the uncompleted also"* | 1·2b (image 5) | narrows ruling 15 |
| 18 | 2026-09-24 | **The back office never completes a job; it only accepts.** *Mark complete* and the *Complete* status leave the office; the server must refuse it too (P1.34). Confirms `BR-MET-110`. | *"The signed flow is that the technician completes the job and the office accepts it. - this is correct"* · *"back office cannot complete the job it can only accept it"* | 1·2a′, 2·1a (images 4, 22) | — |
| 19 | 2026-09-24 | **Jobs can be raised in bulk, on units:** one job for each unit ticked. | *"in raise a job the user should be able to raised bulk work order. the work orders should be raised on units."* | 1·4a, 1·4c, 1·4d (images 14, 17, 18) | — |
| 20 | 2026-09-24 | **An asset type chosen means the asset must be chosen.** Given after asking what happens when a unit has two water meters. | *"if asset type is selected then user needs to select asset - update the wireframes ."* | 1·4a′ (image 15) | — |
| 21 | 2026-09-24 | **The premises is a dropdown** — one you can type into, as `BR-SHL-033` already requires of a long list. | *"here premise should be dropdown"* | 1·4a′ (image 15) | — |
| 22 | 2026-09-24 | **The assets list has its own search** — asset no, serial and where. | *"here there should be search for assets"* | 1·4a′ (image 15) | — |
| 23 | 2026-09-24 | **The due date is a date picker.** The 23 Sep *Expected Date* is this date, asked once. | *"here there should be date picker for due date. …"* | 1·4b (image 16) | — |
| 24 | 2026-09-24 | **No Area on the raise:** the job takes its building's. | *"… also area should not be needed as we are attaching premises. …"* | 1·4b (image 16) | — |
| 25 | 2026-09-24 | **A job can be assigned when it is raised, or left blank** — technicians, crews and contractors. | *"… here crew assignment options are missing, user can either assign or can leave blank."* | 1·4b (image 16) | — |
| 26 | 2026-09-24 | **The Crews page leads to adding a crew member, and the add is drawn.** | *"here there in this crew section show the wireframes of how crew members are added. also give an navigation from this page to add crew member."* | 4·1 → 4·1a (images 25, 26) | — |
| 27 | 2026-09-24 | **A technician's jobs and performance can be seen** — the Jobs and Performance tabs, and *This month* on the Overview. | *"here user should be able to view the crew performance, can also view the orders that crew had worked on."* | 4·2a, 4·2b, 4·2d (images 31, 32, 34) | — |
| 28 | 2026-09-24 | **A technician's Certifications tab is drawn** — as a table, with add and renew. | *"here certification tab wireframe is missing"* | 4·2c (image 33) | — |
| 29 | 2026-09-24 | **The Add part form is drawn**, and 5·1b for a refusal. | *"here add form wireframe is missing in the doc."* | 5·1 → 5·1a, 5·1b (images 36, 37) | — |
| 30 | 2026-09-24 | **The Crews page is three lists, not one table** — Technicians · Crews · Contractors. ⚠ It supersedes the last sentence of `BR-WRK-028` (CONFIRMED), *"A crew and a contractor are rows in the same table as a person."* | *"here user is unable to understand the crew and the technicians - can you make it simple to understand for the user - as one table is confusing."* | 4·1, 4·1b, 4·1c (images 25, 27, 28) | `BR-WRK-028` (last sentence) |
| 31 | 2026-09-24 | **The Add a crew and Add a contractor forms are drawn.** | *"here crews and contracteos wireframs are missing"* | 4·1 → 4·1d, 4·1e (images 29, 30) | — |
| 32 | 2026-09-24 | **The part has a Name.** It was the same field, called Description. | *"here add name to the part add form."* | 5·1a (image 36) | — |
| 33 | 2026-09-24 | **The Import parts screens are drawn**, from a real run. | *"here import parts creens are missing"* | 5·1a → 5·2a–5·2e (images 38–42) | — |
| 34 | 2026-09-24 | **Seven escalations on the rule, and reminders live in Notifications.** Given on the table put in chat. Who is told follows `BR-NOT-021`. | *"add all these escalations in the wireframe. if reminders can be managed in notifications then remove if needed"* | 7·2d (image 60) | — |
| 35 | 2026-09-24 | **Raised from an account or an asset, the form arrives filled.** The first step of each is drawn; the rest is 1·4b and 1·4c. ⚠ On the asset page it supersedes the Assets blueprint's figure 42 one-page form — `BR-WRK-056` holds. | *"now there are screens missing for the forms where service orders are raised from accounts and from assets- the forms should be auto filled by the information , just the first screen needs in the doc for both"* | 1·4e, 1·4f (images 19, 20) | Assets blueprint figure 42 (the one-page raise form) |
| 36 | 2026-09-24 | **A contractor's people close their own jobs on the phone.** Left to us between phone logins for contractors and the office typing in what a contractor reported. **Phone logins:** the office typing it in would reopen 18 for one kind of job. A contractor's people are added the way a crew's members are (4·1a), each with a phone-only login. Written up in the field-app document. | *"u decide"* (decided by the blueprint's author when the PO left it to us) | 4·1a; field-app document (not in hand) | — |

**Four later rulings already drawn (26 Sep 2026, on the rule builder)** — recorded in the blueprint on 7·2a–7·3c and tasks P3.64–P3.67, not among the 36:

| Date | Ruling (the blueprint's words) | Narrows |
|---|---|---|
| 2026-09-26 | **The rule builder becomes three steps** — Trigger · Notify · Review; the Assignment step is retired (P3.64; images 57, 58, 59, 61). | — |
| 2026-09-26 | **Several triggers on one rule, any of them raises the job** (option B; P3.65; image 57). One subject still gets one open job per template (P3.38). | — |
| 2026-09-26 | **A notification's message is a picker into the notification catalogue, never a text box** (option A; `BR-NOT-017`, one home; image 59). | — |
| 2026-09-26 | **Escalations are rows you add** (P3.67): *Who is told* stays derived — whoever acted, plus System Admins (`BR-NOT-021`) — **and a supervisor may ADD recipients, never remove them** (option B; *Also tell*, e.g. *the area supervisor*; images 59, 61, 62). | `BR-NOT-021` clause (d) — *"no per-rule recipient is settable anywhere"* |

**One discrepancy inside the blueprint, recorded rather than resolved:** its machine manifest lists 37 rulings, and its #4 is *"The raise form carries Job Type\*, Template\*, Priority, Expected Date, Description"* (23 Sep) where the numbered list's #4 is *sign in by email, phone or staff ID*; its #37 is the existing 2026-09-10 ruling *"In the beta a report is a defect by default"*. The numbered list of 36 is used here. The 23 Sep raise-form fields are not lost: ruling 23 says *"Your 23 Sep Expected Date is this date, asked once"*, and task P2.2 carries the five fields.

## 1 · Classified

**MAINTENANCE, with change carried** (`12-governance/22-product-maintenance-process.md`). A clerk can list, open, edit, approve, crew, stock, template and rule work orders today, so a live module redrawn end to end is maintenance, borrowing only the drawing step from Build — **REPRODUCE, LOCATE and BLAST RADIUS come before any fix**, against the build running at go, not the `2.340.0` the drawings were captured on. Screen faults the blueprint found are **defects** by default (PO 2026-09-10, *"CR is change in product, defect is product does not do what is expected"*); its 34 beta observations are reports and are filed as defects at go. What the product never did — raise in bulk on units, raise from an account or an asset filled, three crew lists with add forms, a technician's Jobs / Certifications / Performance tabs, parts import, a rule detail page, seven escalations that fire, notifications to the consumer and the back office, printing — is **change**, carried here.
**Fast path does not apply:** it touches stored rows (acceptance columns, hold reasons, SLA pause, contractor phone and email, notification rule rows), the acceptance money path (cost lines and meter reads are written at acceptance — P1.6, P1.32) and a signed refusal on the server (P1.34).

## 2 · What signed statements it touches

Each quoted from the repository as it reads on 2026-10-04, with its supersedes chain. **No ❄️ B4/B5 figure and no CONFIRMED `BR-RAT` rule moves.**

* **`BR-WRK-029`** (CONFIRMED — `WS-23`): *"**Dispatch offers only a technician, crew or contractor whose skills match the template's skill.** The same test decides for all three."* → **SUPERSEDED by ruling 2 (2026-09-23): the skill match ADVISES and never blocks.** Every name stays choosable; beside each the skill, the area, off that day, jobs that day, *Best fit* first (P4.5, P4.12, images 12, 13, 16). The override is audited (P4.6). Stamped on the rule in `04-docs/05-modules/16-work/02-business-rules.md` in this commit.
* **`BR-WRK-030`** (CONFIRMED 2026-09-04 → `OQ-WRK-1493`, *"(c) per-tenant, default warn"*): a lapsed certification blocks or warns by the tenant's setting. → **NARROWED by ruling 2** as to what *block* may do; **whether a tenant with a regulator may still block on a LAPSED CERTIFICATION, as opposed to a missing skill, is left OPEN by the blueprint** and is not resolved here. Stamped with the open point.
* **`BR-WRK-028`** (CONFIRMED — `WM-13`; `WS-23`, `WS-24`), last sentence: *"**A crew and a contractor are rows in the same table as a person.**"* → **SUPERSEDED by ruling 30 (2026-09-24): the Crews page is three lists — Technicians · Crews · Contractors**, each its own table with its own add button (images 25, 27, 28, 29, 30). The rest of the rule (a technician is a profile beside an `identity.User`, invited in Settings → Team) **STANDS**. Ruling 36 adds that a contractor's people get phone-only logins, added the way a crew's members are. Stamped.
* **`BR-WRK-056`** (CONFIRMED — `WM-43`, amended 2026-09-06): *"**The Assets door is ONE form with four ways in** — `/{tenant}/assets/{assetId}/work-orders/new` …"* → **STANDS** (one form, four ways in, `work_orders.asset_id`, templates filtered by asset type). **What ruling 35 supersedes is the Assets blueprint's figure 42 one-page raise form** (`04-docs/05-modules/05-assets/conformance/CR-092-lane4-actions-step2.md`: *"Figure 42 draws the raise footer as `Cancel · Raise work order ✓`"*): raised from an asset, the form is the Work raise arriving filled — 1·4f (image 20), then 1·4b and 1·4c. Task P2.21 adds that an asset is offered its own SERVICE's templates too. Stamped as a dated note, rule unchanged.
* **`BR-WRK-033`** (CONFIRMED — `WM-24`, `WS-26`): *"A rule has a trigger, assignment logic, notifications, reminders & escalation and an enabled flag …"* → **NARROWED by ruling 34 (reminders live in Notifications, not on the rule; seven escalations on the rule) and by the 26 Sep rulings** (three steps — Trigger · Notify · Review; several triggers, any of them; *who to give the job to* asked on the Trigger step, the Assignment step retired). *A rule that is off raises nothing* and *every rule-raised order carries the rule as its source* **STAND**. Stamped.
* **`BR-NOT-021`** (CONFIRMED — PO 2026-08-17, *"11 - A ✅ the user who started the action, plus all System Admins for failures"*): clause (d) — *"**no per-rule recipient is settable anywhere** — `rule_service` refuses every spelling of \"send it to X\" quoting this rule"*. → **Ruling 34 FOLLOWS it** (*"Who is told follows BR-NOT-021"*); the **26 Sep ruling, option B, NARROWS clause (d) for Work escalations only**: *who is told* stays derived, and a supervisor may **ADD** recipients (*Also tell*), never remove the derived ones. ⚠ **Not stamped on `BR-NOT-021` in this commit** — that rule is the Notifications module's, and whether the PO was shown that option B reverses clause (d)'s refusal is not on the page; it goes to the PO as a one-line confirmation before P3.67 is built (§3 surface 8).
* **`BR-NOT-017`** (one home for every notification rule and its wording; PO 17 Aug, *"we bring all internal external notification rules at one place and they are part of notification settings"*) → **STANDS; rulings 34 and the 26 Sep message picker apply it** — the rule form reads the catalogue's messages and owns none.
* **`BR-PAY-036`** (CONFIRMED — PO TR-1, 2026-08-08): *"**Payment is ALWAYS accepted** … acceptance NEVER auto-changes account status — restoration stays an explicit, audited staff action"*. → **STANDS; ruling 10 obeys it.** The blueprint corrects the list shown to the PO on 24 Sep, which said a payment could book a reconnection: *a payment alone can never book a reconnection*; the rule's visit arrives ticked on the clerk's own reconnect act. This answers the first half of `OQ-WRK-1726` (*is Reconnect after payment a rule we want?* — yes, in that shape only); **the register row stays OPEN** until the PO's go fans it out, because its second half (who builds the trigger) is the build's.
* **`BR-MET-110`** (PO 2026-08-25, *"Work order will send the data and confirm from field; utility staff will review these work order , accept them …"*) → **CONFIRMED again by ruling 18**: the back office never completes a job, it only accepts. P1.34 makes the server refuse a completion from anyone but the job's technician (or, by ruling 36, a member of the crew or contractor it was given to).
* **`BR-SHL-033`** (a long list is a dropdown you can type into) → **STANDS; ruling 21 applies it** to the raise form's premises.
* **`BR-WRK-022`** (areas are `tenancy.Area`, never minted by Work) → **STANDS**; ruling 24 stops ASKING for an area on the raise — the job takes its building's (P2.17).
* **`OQ-WRK-1497`** (CLOSED 2026-09-04, *"three separate assignments"*) → **STANDS and governs ruling 19**: a bulk raise is separate jobs, no batch number.
* **B14 rules 2, 3, 31, 33, 35, 37, 42, 43, 44** — applied, not changed (ruling 16 is rule 2; ruling 1's eleven catalogue values are rule 35).

## 3 · Impact across the ten surfaces

| # | Surface | Impact |
|---|---|---|
| 1 | Screens | Every Work back-office screen: `OrdersPage.tsx` (790 lines today), `OrderDetailPage.tsx` (1,139), `OrderEditPage.tsx` (509), `NewOrderWizard.tsx` (292), `AwaitingApprovalPage.tsx` (389), `MapView.tsx` (221), `CrewsPage.tsx` (394), `PartsPage.tsx` (333), `AddPartModal.tsx` (176), `TemplateBuilder.tsx` (1,569), `TemplateDetailPage.tsx` (483), `RulesPage.tsx` (298), `RuleBuilder.tsx` (326), `PerformancePage.tsx` (280) — all under `07-frontend/src/features/work/`. New: raise from an account / an asset (1·4e, 1·4f), raise result (1·4d), Approvals accept (2·1a/b), Add crew member / crew / contractor (4·1a, d, e), technician Jobs and Performance (4·2b, d), Import parts (5·2a–e), a rule's own page (7·3a–c). Named and not drawn: the at-risk board, the schedule board, bulk raise across buildings (P5). |
| 2 | API | Raise many in one press (P2.12) with a per-job answer; a unit must be in the job's building (P2.13); assets of a set of units by type and service, paged (P2.16 — *NOT SERVED* today); assign at creation (P2.5); the customer's name and phone through the seam (P1.15); the signature's mark as a four-hour link (P1.23); readings that are words (P1.33); **the server refuses an office completion** (P1.34); send a completed job back to the field (P4.14); rule processes served once (thirteen, P3.30); several triggers (P3.65); seven escalations that fire (P3.57); consumer and back-office notifications (P6.1, P6.2); a work-order PDF (P6.3). |
| 3 | Data | P0.2 acceptance columns (`accepted_by_technician`, `accepted_at_technician`, `declined_reason` — NOT the existing supervisor `accepted_by`); P0.3 hold reason and expected return (a CHECK makes a later value a migration — decide first); P0.4 hold-reason lookup; P3.53 a contractor's phone and email; P3.23 indexes for server paging; P5.8 SLA pause columns; P6.7 notification rule rows; P0.1 a data task (0 of 39 demo orders carry a priority). Every new tenant table gets RLS `FORCE` in its own migration (CLAUDE.md hard rule 1, `CR-070` §3); 🔒 migration ordering. |
| 4 | Business rules | §2: `BR-WRK-029` superseded; `BR-WRK-028` last sentence superseded; `BR-WRK-030`, `BR-WRK-033` narrowed; `BR-WRK-056` note (figure 42); all stamped in this commit. `BR-NOT-021` (d) narrowed by the 26 Sep ruling — stamped only after the PO's one-line confirmation. |
| 5 | Billing / money | No rate, bill or ledger figure moves. **The acceptance path IS a money path**: acceptance persists cost lines and turns a reading into a meter read (`apps/work/api.py`, `asset_door.py`) — P1.6 (an accepted order stays findable) and P1.32 (Accept on the order page) must be proved on PostgreSQL (hard-won law 14), and no reading may become a meter read before acceptance. Parts unit cost stays 4 decimals stored, 2 shown (hard rule 2). |
| 6 | Tests | The order page's tab list is asserted (`OrderDetailPage.test.tsx`, six ids — changes by design with P1.21); tests that complete a job from an office session go red by design with P1.34; the rule builder's five steps become three. Each is rewritten case by case in the task that changes the screen, never deleted; a case guarding a stored fact is re-pointed. New journeys named by the blueprint: `dispatcher-reassigns.md` (extended), `raise-a-job.md`, `supervisor-writes-a-rule.md`, `technician-accepts.md` (shared with the field-app document), `sla-breach.md`, `customer-told-about-a-visit.md`. |
| 7 | Languages | All eleven catalogues. Ruling 1: eleven catalogue VALUES for *Approvals*, each written in its own language (B14 rule 35); the `work.approvals.*` keys stay. Every new screen's strings; retired keys through `10-scripts/i18n_fanin.py`. |
| 8 | Open questions | **Answered by consequence (fan out at go, not now):** `OQ-WRK-1726`'s first half (ruling 10). **Re-opened or newly raised by the blueprint, to be minted at go and stubbed with their ids, never resolved by a lane:** a map tile source (P3.3 — a third-party key and a monthly cost); what *SLA met* means when an order has no due date and no priority (P5.1); whether a regulated tenant may still block on a lapsed certification (`BR-WRK-030`); a task's instruction text (6·3c — a new column); the PO's confirmation that the 26 Sep *Also tell* option narrows `BR-NOT-021` (d). |
| 9 | Demo fixture | `apps/work/sample_data.py` / `load_sample_data --tenant brazosbend`: priorities on existing orders (P0.1); 42 of 43 demo jobs name no account (P1.15); accepted demo jobs read *Queued* (P1.31); the rules the fixture seeds must match the thirteen processes and the labels the order table accepts (P3.31, `DEF-WRK-4096`); fixing labels alone would switch on a leak rule catching 98 meters (51 electric) — measured by the blueprint on 24 Sep. |
| 10 | Other modules | Customers (the seam serves the holder's name and phone, P1.15; raise from an account, 1·4e), Assets (raise from an asset, 1·4f; P3.22 the page behind the asset's button), Metering (acceptance and meter reads, `BR-MET-110`; the field-result endpoint is metering's), Notifications (six escalation messages and four consumer kinds in the catalogue, P3.58, P6.5; reminders, P3.59), Identity (phone-only logins for a contractor's people, ruling 36 — field-app document), Tenancy (areas, services — eleven, fire at position 11). Work writes none of their tables (`BR-WRK-002`, `G78`). |

## 4 · What is built today and becomes wrong — re-measured on `2.490.6`, state by state (lane WORK-CR, round 1)

**How.** Build **`2.490.6`** (worktree at `f29deab02`, then `bd353f651`); API `runserver 127.0.0.1:8311` on a private
PostgreSQL 16 database `sbh_workcr` (`migrate` + `seed_demo` + `load_sample_data --tenant brazosbend`, the tenant the
65 images were captured on); SPA `vite build --mode wolocal` served on `5411`; signed in as Dana, System Admin;
Chromium at 1440 wide. Five walk phases, `10-scripts/cr168_work_before_walk.mjs` with `…_phase1.mjs`–`…_phase5.mjs`
(phase 1 opens every address; 2–5 press what a clerk presses: two orders ticked, the bulk dialogs, garbage typed into
Reschedule, the edit save as a person, a crew and a contractor, the office ticking WO-0037's checklist and pressing
*Mark complete*, the Approvals eye, an accept, a technician's first sign-in, one raise through the wizard, and Import
parts run end to end with `08-qa/work-2026-10-04/parts-import-walk.csv`). **59 photographs** in
`08-qa/work-2026-10-04/before/`, every one opened and checked not blank; their file names are cited below.
The photographs are taller than the screen because the viewport was set tall (the app frame scrolls its own column);
the drawings are full-page renders of the same frame.

**Writes the walk made** (so a later reader of `sbh_workcr` is not misled): WO-0018 assigned to D. Ortiz; WO-0029 put
on hold; WO-0037's checklist ticked by the office, marked complete and then accepted through
`POST /work-orders/{id}/accept`; WO-0041 raised through the wizard; parts MTR-W34, GSKT-STD and SEAL-01 imported; a
draft template *Walk template — CR-168* was **not** saved (the walk stopped at Review). D. Ortiz received a temporary
password.

**LOCATE — the files actually mounted** (from `07-frontend/src/App.tsx`, not from names):

| Route | Mounted | Inside `WorkShell`? |
|---|---|---|
| `/work`, `/work/orders` | `features/work/OrdersPage.tsx` (+ `dispatchModals.tsx` for the bulk dialogs) | yes, `tab="orders"` |
| `/work/orders/:orderNo` | `features/work/OrderDetailPage.tsx` | no |
| `/work/orders/:orderId/edit` | `features/work/OrderEditPage.tsx` | yes, `tab="orders"` (the strip is not drawn on this page) |
| `/work/orders/new` | `features/work/NewOrderWizard.tsx` | no |
| `/assets/:assetId/work-orders/new` | `features/assets/RaiseWorkOrderPage.tsx` (WRK-24) | no |
| `/accounts/:id?tab=work` → *⚡ Raise work here* | `features/work/buildViews.tsx` `WorkOrdersTab` → `NewOrderWizard` with no subject (`DEF-WRK-4752`) | — |
| `/accounts/:accountId/work-orders/new` (drawn, 1·4e) | **not routed** — *"This screen is not built yet"* (`a19-account-raise.png`) | — |
| `/work/awaiting-approval` | `features/work/AwaitingApprovalPage.tsx` | yes, `tab="approvals"` |
| `/work/map` | `features/work/WorkMapPage.tsx` → `MapView.tsx` | yes, `tab="map"` |
| `/work/crews` | `features/work/CrewsPage.tsx` | yes |
| `/work/crews/:slug` | `features/work/TechnicianDetailPage.tsx` (+ `SkillsWizard.tsx`) | no |
| `/work/parts` | `features/work/PartsPage.tsx` + `AddPartModal.tsx` | yes |
| `/work/parts/import` | `ImportWorkflowPage target="parts"` (the shared five-stage runner) | no |
| `/work/templates` | `features/work/TemplatesPage.tsx` | yes |
| `/work/templates/:templateId` | `features/work/TemplateDetailPage.tsx` | no |
| `/work/templates/new`, `/work/templates/:id/edit` | `features/work/TemplateBuilder.tsx` | no |
| `/work/rules` | `features/work/RulesPage.tsx` | yes |
| `/work/rules/new` | `features/work/RuleBuilder.tsx` | no |
| `/work/rules/:ruleId` (drawn, 7·3) | **not routed** — *"This screen is not built yet"* (`a62-rule-detail.png`) | — |
| `/work/performance` | `features/work/PerformancePage.tsx` | yes |

**The 65 drawn states against today.** *Matches* = today's screen is what the drawing records as the product on
`2.340.0` (where the image carries red dashes, those changes are still to build). *Differs* = today's screen is not
what the drawing records as current (drift since `2.340.0`, or a capture the drawing shows that today's product does
not reach). *Not built* = the drawn state cannot be reached today. *Already built* = the drawn change is live.

| # | State | Today on `2.490.6` | Class | Photo |
|---|---|---|---|---|
| 01 | Orders | Tabs read *Awaiting approval* (ruling 1 not built); the five tiles wrap so *Overdue* sits alone on a second row; *+ New work order* is outlined under the pager, not top right (`DEF-WRK-9562`); every row's Priority is *—* (`DEF-WRK-9571`); the search shows two clear crosses (`DEF-SHL-5345`) | Differs | `a01-orders-list`, `b11-reschedule-garbage`, `b03-search-clear` |
| 02 | Assign in bulk | Bar reads *2 orders selected · Assign selected… · Reschedule selected… · Change priority… · Clear*; the dialog *Assign the selected orders* has **Who is going** only — no date, window, advice or count | Matches (dashed change not built) | `a02-bulk-assign` |
| 03 | Order · Overview, not completed | **Partly built:** Reassign…, Put on hold…, Cancel order sit top right since `2.445.13`, but **Mark complete** leads them (ruling 18 removes it); six tabs; Overview holds Type, Service (lower-case *water*), Raised by, Template version — no meter, unit, customer, window or due; the header line is *240 Sable Court · D. Ortiz* | Differs | `a03-order-overview` |
| 04 | Order · Overview, completed | After the office's own *Mark complete*: pills *Scheduled · Completed*, the same four head buttons (Mark complete live again), no Send back / Accept, no Outcome, Closed by or Signature | Differs | `a04-order-completed-overview` |
| 05 | Checklist, not completed | Safety and tasks are **tickable checkboxes for the office**; tasks a list, not a table; ranges `18.0000–96.0000`; an *EFFECT · Marking complete* panel under every tab | Differs | `a03-order-checklist` |
| 06 | Checklist, completed | No Done column, no who/when, no photo thumbnails; the office closed it with **0 of 3 required photos** | Differs | `a04-order-completed-checklist`, `b18a-office-ticked-checklist` |
| 07 | Parts | Part · Planned · Used; `1.0000 roll` | Matches | `a03-order-parts` |
| 08 | Audit | Act · Who · When only; **When is raw ISO** (`2026-10-04T05:38:42.963368+00:00`) and Who names the technician for the dispatcher's act (`DEF-WRK-9584`); holds and cancels absent (`DEF-WRK-9532`) | Differs | `a03-order-audit` |
| 09 | Photo viewer | No viewer on the office page; the demo has no field photograph to open | Not built | — |
| 10 | Put on hold | **No dialog** — pressing *Put on hold…* holds at once (`POST …/hold {}`), toast *Put on hold.*; no reason, back-on date or note | Not built | `a10-put-on-hold` |
| 11 | Cancel order | Dialog matches; its other button reads *Cancel*, not *Keep the order* | Matches (dashed change not built) | `a11-cancel-dialog` |
| 12 | Assign a job | Edit page: buttons at the **bottom-left** (*Cancel · Cancel work order · Save changes*); Status offers *Complete*; Assigned to a plain select with no advice; Date `type=date` (no *Today*); Window *Any time / 08:00–12:00 / 12:00–17:00 / Exact appointment*; Area | Differs | `a12-edit-unassigned` |
| 13 | Reassign a job | The same page opens an assigned job (WO-0037, D. Ortiz) on **Assigned to: Nobody yet** (`DEF-WRK-9530`); no *Why it moves*; saving a crew or contractor 404s with no message (`DEF-WRK-9563`) | Differs | `a13-edit-assigned`, `b04-edit-save-Field-crew-A-`, `b04-edit-save-Redline-Meter-Services`, `b04-edit-save-D-Ortiz` |
| 14 | Raise · on units | 3-step rail matches; **Premises and Job type are free-text boxes**, Template a flat select; no units table; Continue on nothing → *Premises and type needed.* (`DEF-WRK-9572`) | Not built | `a14-raise-1`, `b16a-raise-continue-empty` |
| 15 | Raise · asset type chosen | No asset type or asset control | Not built | `a14-raise-1` |
| 16 | Raise · Schedule & crew | Step 2 is *Due* (a date box, *Leave empty to use the priority's own target.*) and *Area* — no visit, no assign | Not built | `a16-raise-step2` |
| 17 | Raise · Confirm | Step 3 is one *EFFECT · Raising this order* panel and *Raise work order ✓* — no summary, no jobs table | Not built | `a17-raise-step3` |
| 18 | Raise · Result | The press opens the new order's page (WO-0041) with a toast; no result table | Not built | `a18-raise-after-press` |
| 19 | Raise from an account | The drawn address is not routed; the account's Work tab has *⚡ Raise work here*, which opens the blank wizard (`DEF-WRK-4752`) | Not built (a door exists) | `a19-account-raise`, `b22b-account-work-tab` |
| 20 | Raise from an asset | One-page form (figure 42's shape, superseded by ruling 35): Template* and *Cancel · Raise work order ✓*, two CHECK panels | Differs (built to the superseded shape) | `a20-asset-raise`, `b23a-asset-page` |
| 21 | Approvals | Title and tab *Awaiting approval*; no Select column, no ✓ Accept; the eye opens the **premises' build tab** (`DEF-WRK-9575`); an office-completed row shows Outcome *—* | Matches (dashed changes not built) | `a21-approvals`, `a21b-approvals-one-row`, `b18c-approvals-eye-destination` |
| 22 | Approvals · Accept | No accept on the queue | Not built | — |
| 23 | Approvals · Accepted | Accepting (through the API) empties the queue and the order then **cannot be found** on Orders (`DEF-WRK-9569`) | Not built | `b10-accepted-order-searched` |
| 24 | Map | Five pins on a blank ground, as drawn (tile source `OQ-WRK-12787`); a pin opens the order's **edit** page (`DEF-WRK-9576`) | Matches | `a24-map`, `b19-map-pin-click` |
| 25 | Crews · Technicians | **One table of seven rows** — four people, two crews, one contractor — with a rationale line under it; no add button; no segmented views | Differs | `a25-crews` |
| 26 | Add crew member | No door | Not built | `a25-crews` |
| 27 | Crews · Crews | No view | Not built | — |
| 28 | Crews · Contractors | No view | Not built | — |
| 29 | Add a crew | No form | Not built | — |
| 30 | Add a contractor | No form | Not built | — |
| 31 | Technician · Overview | Tabs *Overview · Certifications*; skills table as drawn; no crew or open-job count in the head; no *This month* | Matches (dashed changes not built) | `a31-tech-overview` |
| 32 | Technician · Jobs | `?tab=jobs` falls back to Overview (the page is byte-identical) | Not built | `a31-tech-overview` |
| 33 | Technician · Certifications | A line of names with expiry dates; no table, add or renew | Matches (dashed changes not built) | `a31-tech-certifications` |
| 34 | Technician · Performance | `?tab=performance` falls back to Overview | Not built | `a31-tech-overview` |
| 35 | Parts | As drawn: *↑ Import parts · + Add part* top right, Register / Issue log (held), search, ▦, six columns; no row action, no filter (`DEF-WRK-9578`–`9580`) | Matches | `a35-parts` |
| 36 | Add a part | Second field is **Description**, not Name; unit-cost help *Kept to four decimals, shown as two.* | Matches (dashed change not built) | `a36-add-part` |
| 37 | Add a part — refused | *String must contain at least 1 character(s)* ×3 and *Invalid* (`DEF-WRK-9585`); *Fix 4 fields to continue.* | Differs | `a37-add-part-empty` |
| 38 | Import · Extract | As drawn (four source cards, drop zone, sample CSV, the Category hint) | Matches | `a38-parts-import` |
| 39 | Import · Transform | Columns matched, but **Sample value is empty** and *Rows forward to validation 0* over a 5-row file (`DEF-WRK-9588`) | Differs | `a39-import-transform` |
| 40 | Import · Validate | 5 · 3 · 2 · 0 · 3 as drawn; the rule reads *Every part needs a description.*; *Category — blank in all 5 rows* although the file carries one (`DEF-WRK-9587`); Key column blank | Differs | `a40-import-validate` |
| 41 | Import · Load | As drawn (dry run 3/0/2, approval, rollback point, *Commit load ✓*) | Matches | `a41-import-load` |
| 42 | Import · Result | 3 loaded / 2 rejected; Key blank; *Your utility requires unit on every premises.* on a part | Matches (dashed changes not built) | `a42-import-result` |
| 43 | Templates | As drawn | Matches | `a43-templates` |
| 44 | Template · Overview | Nine counts (*Safety lines 2 · Tasks 6 …*) — no section panels, no Edit per section | Matches (dashed change not built) | `a44-template-overview` |
| 45 | Template · Usage | *0 orders raised across 2 versions* | Matches | `a44-template-usage` |
| 46 | Template · Versions | As drawn; seeded versions carry a note, a builder publish would not (`DEF-WRK-9568`) | Matches | `a44-template-versions` |
| 47 | Template · Audit | *The change history opens with the next release.* | Matches | `a44-template-audit` |
| 48 | Builder · Details | As drawn (packs, Name, Service, Job type, asset types, skill, crew size, safety kit, four ticks); no scope (`DEF-WRK-9577`) | Matches | `a48-builder-details-filled` |
| 49 | Builder · Safety | Added rows are plain text (`DEF-WRK-9566`) | Matches (dashed change not built) | `a49-safety` |
| 50 | Builder · Tasks | Added rows are plain text (`DEF-WRK-9565`); no instruction text (PO answer 3, new) | Matches (dashed change not built) | `a50-tasks` |
| 51 | Builder · Materials | Plain text; quantity `1.0000` | Matches (dashed change not built) | `a51-materials` |
| 52 | Builder · Readings | Plain text; *Yes — posts on approval* chip as drawn | Matches (dashed change not built) | `a52-readings` |
| 53 | Builder · Help | Kinds *Document · Phone · Note*; *Where to find it* typed; no upload, no Link (`DEF-WRK-9567`) | Matches (dashed change not built) | `a53-help` |
| 54 | Builder · Signature | As drawn (Keep) | Matches | `a54-signature` |
| 55 | Builder · Review | A seven-row table of section counts with ✎; no detail (rulings 7, 9) | Differs | `a55-review` |
| 56 | Rules | No *+ New rule*, no Last fired, no row actions; *Turn off / Turn on* per row; search dead (`DEF-WRK-9564`, `9573`) | Matches (dashed changes not built) | `a56-rules`, `b15-rules-search` |
| 57 | Rule · Trigger | Five-step hand-rolled rail (`DEF-WRK-5066`); Rule name, Source module, one trigger sentence, Template raised; *Back* / *Next* | Not built | `a57-rule-step1` |
| 58 | Rule · Assignment (retire) | Live as step 2: *Give the job to* — Nobody yet / area / skill | Retire | (walk text, `a57-rule-step1` rail) |
| 59 | Rule · Notify | Step 3 is one tick, *Tell the customer a visit is coming* | Not built | — |
| 60 | Rule · Escalation (retire) | Live as step 4: *Escalate after (hours)* | Retire | `a57-rule-step4` |
| 61 | Rule · Review | Step 5: *Every night it looks for … and raises …* and *Activate rule* | Not built | — |
| 62–64 | A rule's own page (Overview, Jobs, Audit) | Not routed | Not built | `a62-rule-detail` |
| 65 | Performance | As drawn — and the headline says *SLA met 100.0%* over rows where six of seven types read 0.0% (`DEF-WRK-9586`) | Matches | `a65-performance` |

**Count (65 states):** **Matches 26** (12 exactly as drawn; 14 whose red-dashed changes are still to build) ·
**Differs 14** · **Not built 23** (62–64 counted as three) · **Retire 2** (58, 60 — live today as steps 2 and 4,
removed by the 26 Sep rulings) · **Already built 0** — one partial: the order page's actions top right (`2.445.13`),
the same commit that put *Mark complete* in front, which ruling 18 removes.

**What changed since `2.340.0` that the drawing does not know.** (1) *Mark complete* was moved to the page head on
2 Oct (`61d24d572`, `2.445.13`) — ruling 18 removes it, and the walk proved the office can still tick a job's whole
checklist and close it with 0 of 3 required photos (`DEF-WRK-9525`, filed by WORK-SRV; screen evidence
`b18a-office-ticked-checklist`). (2) The Orders tiles now wrap at 1440. (3) The account's Work tab grew a
*⚡ Raise work here* door (`DEF-WRK-4752` open). (4) Import parts gained the *Category* hint the drawing shows
dashed (38). Nothing else the blueprint drew as current has moved.

**Data already written that the new screens must read correctly** (unchanged from the draft above, re-measured):
**0 of 40** demo orders carry a priority, **3 of 40** a due date (§7.1, P0.1); 23 completed demo jobs read *Queued* or
*On site* (`DEF-WRK-9526`); builder-made templates save as premises scope (`DEF-WRK-9528`, `DEF-WRK-9577`); rules
stamp labels the order table refuses (`DEF-WRK-4096`). **Lanes building on Work right now:** none (WORK-SRV is done,
`2f2fc75ed`).

| What | Where | Today (re-measured 2026-10-04 on `2.490.6`) | Becomes |
|---|---|---|---|
| Order page tabs | `OrderDetailPage.tsx` `ORDER_DETAIL_TABS` (line 224) | Six: `overview · checklist · parts · location · customer · audit` | Four (ruling 12, P1.21) |
| *Mark complete* | page head (`2.445.13`) and the edit page's Status *Complete* | Present, and it closes a job with 0 of 3 required photos | **Removed** (ruling 18, P1.34; server half `DEF-WRK-9525`) |
| Skill match | `apps/work/dispatch.py:748-770` | Refuses (`DEF-WRK-9533`); the edit page offers every name and 404s on a crew (`DEF-WRK-9563`) | Advice, never a block (ruling 2, P4.5) |
| Approvals eye | `AwaitingApprovalPage.tsx:276` | Opens the premises' build tab | Opens the order (P1.5) |
| The raise | `NewOrderWizard.tsx` | Free-text premises and type; Due + Area on step 2 | Rulings 19–25 (P2) |
| Crews | `CrewsPage.tsx` | One table of seven mixed rows | Three lists (ruling 30) |
| Rule builder | `RuleBuilder.tsx` | Five steps, hand-rolled rail, one trigger | Three steps on `WizardFrame` (26 Sep) |
| Template builder rows | `TemplateBuilder.tsx` | Plain text after Add in five steps | Editable (ruling 5); tasks gain instruction text (PO answer 3) |

## 5 · The field map — every control on today's Work back office → its home in the 65 images (lane WORK-CR)

**How it was built:** every control was read off the running screens by the walk's `CONTROLS` and `BUTTONS` dumps
(`10-scripts/cr168_work_before_walk*.mjs`; the printed output is not committed — re-run the scripts to see it), not
from the source. The home is the IMAGE named (B14 rule 42). *Retired* = a ruling removes the control; it is listed so
nothing is lost silently. Display-only facts (tiles, columns) are covered by §4's state table.

### 5.1 Orders (1·1) and its bulk dialogs

| # | Today | New home | Image |
|---|---|---|---|
| O1 | Tab strip *Orders · Awaiting approval · Map · Crews · Parts · Templates · Rules · Performance* | the same, *Approvals* (ruling 1) | 01, 21 |
| O2 | Search *order, address…* | Search | 01 |
| O3 | *All* chip | *All* | 01 |
| O4 | *+ Filter ▾* — Type · Status · Priority · Technician · Area | *+ Filter ▾*; Type as a two-level list (P2.3); Status without *Complete*-by-office (ruling 18) | 01 |
| O5 | ▦ column chooser (↑ ↓ per column, *Reset table*) | ▦ | 01 |
| O6 | Select tick per row | Select column (+ select all across pages, P3.6) | 01, 02 |
| O7 | Bulk *Assign selected…* → *Who is going* select | *Assign selected…* → *Assign N orders*: Who is going (with advice), Date, Window | 02 |
| O8 | Bulk *Reschedule selected…* → Date, Window opens, Window closes (free text) | **no drawn home** | — |
| O9 | Bulk *Change priority…* → Priority select | **no drawn home** | — |
| O10 | Bulk *Clear* | the bulk bar | 02 |
| O11 | Row 👁 *Open WO-…* | 👁 | 01 |
| O12 | Row ✎ *Edit WO-…* | ✎ → Assign / Reassign page | 01, 12, 13 |
| O13 | *+ New work order* (under the pager) | *+ New work order*, page head, accent | 01 |
| O14 | Rows per page + ‹ › | pager | 01 |

### 5.2 One order (1·2), its dialogs, and the edit page (1·3)

| # | Today | New home | Image |
|---|---|---|---|
| D1 | *← Orders* | *← Orders* | 03 |
| D2 | *Mark complete* (page head) | **Retired** — ruling 18; a completed job shows *Send back… · Accept ✓* instead | 04 |
| D3 | *Reassign…* | *Reassign…* | 03 |
| D4 | *Put on hold…* (no dialog) | *Put on hold…* → Reason*, Back on, Note | 03, 10 |
| D5 | *Cancel order* → dialog *Cancel* / *Cancel this order* | *Cancel order* → *Keep the order* / *Cancel this order* | 03, 11 |
| D6 | Tabs Overview · Checklist · Parts · Location · Customer · Audit | Overview · Checklist · Parts · Audit; Location and Customer as Overview panels | 03 |
| D7 | Checklist: safety ticks, live for the office | **Retired** — ruling 18; the record shows ✓ who · when | 05, 06 |
| D8 | Checklist: task ticks, live for the office | **Retired** — ruling 18; Done column | 05, 06 |
| E1 | Edit · Status (Queued … *Complete* … Canceled) | Status, without *Complete* | 12, 13 |
| E2 | Edit · Priority | Priority | 12 |
| E3 | Edit · Assigned to (plain select) | Assigned to — searchable, advice on every name, *Best fit* | 12, 13 |
| E4 | Edit · Date (`type=date`) | Date + *Today* | 12 |
| E5 | Edit · Window (Any time / 08–12 / 12–17 / Exact appointment) | Window; *Exact appointment* + a time | 12, 13 |
| E6 | Edit · Area | Area, *From the premises.* | 12, 13 |
| E7 | Edit · Notes for the technician | the same | 12, 13 |
| E8 | Edit · *Cancel* (bottom) | *Cancel*, top right | 12 |
| E9 | Edit · *Cancel work order* (bottom) | *Cancel work order*, top right | 12 |
| E10 | Edit · *Save changes* (bottom) | *Assign ✓* / *Reassign ✓*, top right | 12, 13 |

### 5.3 The raise (1·4) and its two doors

| # | Today | New home | Image |
|---|---|---|---|
| N1 | Step 1 · Premises* (free text) | Premises* — a typeable dropdown | 14, 15 |
| N2 | Step 1 · Job type* (free text) | Job type* — a two-level picker | 14 |
| N3 | Step 1 · Template (flat select) | Template* | 14 |
| N4 | Step 1 · the utility's own fields on a work order (CR-161 W4, none set on the demo) | **no drawn home** | — |
| N5 | Step 2 · Due | Due date (picker, *From the priority — 72 h.*) | 16 |
| N6 | Step 2 · Area | **Retired** — ruling 24 (the job takes its building's) | 16 |
| N7 | *Back* / *Continue* | the same | 14–17 |
| N8 | Step 3 · *Raise work order ✓* | *Raise N jobs ✓* | 17 |
| A1 | Asset door · Template* | 1·4f Template* (*Water templates for a meter.*) | 20 |
| A2 | Asset door · *Cancel* / *Raise work order ✓* | *Continue* → 1·4b, 1·4c | 20 |
| A3 | Account Work tab · *⚡ Raise work here* (×2) | opens 1·4e, *From the account* | 19 |

### 5.4 Approvals (2·1) and Map (3·1)

| # | Today | New home | Image |
|---|---|---|---|
| AP1 | Row 👁 (opens the premises) | 👁 → the order | 21 |
| AP2 | Empty state *Open work orders* (held, *The field closes these, not here.*) | the empty state, released (P1.7) — not drawn, the drawing is the queue populated | — (21) |
| AP3 | ▦ column chooser | **no drawn home** | — |
| AP4 | Rows per page + ‹ › | pager | 21 |
| M1 | 17 pins, one button each | pins, clustered; a pin opens the order | 24 |

### 5.5 Crews (4·1), one technician (4·2), Parts (5·1) and Import parts (5·2)

| # | Today | New home | Image |
|---|---|---|---|
| C1 | Search *name or skill…* | a search per view | 25, 27, 28 |
| C2 | ▦ column chooser | **no drawn home** | — |
| C3 | A person's name → their page | the name | 25 |
| C4 | Rows per page + ‹ › | pager per view | 25, 27, 28 |
| T1 | *← Crews* | the same | 31 |
| T2 | *Assign skills* (opens the skills wizard) | the same | 31 |
| T3 | *Set unavailable* | the same | 31 |
| T4 | Tabs Overview · Certifications | Overview · Jobs · Certifications · Performance | 31–34 |
| P1 | *↑ Import parts* | the same | 35 |
| P2 | *+ Add part* | the same | 35 |
| P3 | Register / Issue log (held) | the same, Issue log released (P3.11) | 35 |
| P4 | Search *part #, description…* | Search | 35 |
| P5 | ▦ | ▦ | 35 |
| P6 | Rows per page + ‹ › | pager | 35 |
| P7 | Add part · Part number* | Part number* | 36 |
| P8 | Add part · Description* | **Name*** (ruling 32) | 36 |
| P9 | Add part · Category | Category | 36 |
| P10 | Add part · Unit of measure* | the same | 36 |
| P11 | Add part · Unit cost* | the same (*In dollars, like 92.40.*) | 36 |
| P12 | Add part · *Cancel* / *Add part* | *Cancel* / *Add part ✓* | 36, 37 |
| I1 | Extract · four source cards (three held *Not switched on yet*) | the same | 38 |
| I2 | Extract · drop zone / browse | the same | 38 |
| I3 | Extract · *Download a sample CSV* | the same | 38 |
| I4 | Extract · Mapping template | the same | 38 |
| I5 | Extract · Batch label | the same | 38 |
| I6 | Extract · *Insert new only* / *Insert & update* | the same | 38 |
| I7 | *Save mapping as template* (held) | the same | 38–42 |
| I8 | Transform · *Maps to* ×5 | the same | 39 |
| I9 | Transform · three ticks (drop duplicates, keep latest, skip empty) | the same | 39 |
| I10 | Validate · *Fix here…* per reject | the same | 40 |
| I11 | Load · *Change it* | the same | 41 |
| I12 | Load · rollback point, notify, *I approve this load.* | the same | 41 |
| I13 | Load · *Download the N rows that failed* | the same | 41 |
| I14 | Load · *Commit load ✓* | the same | 41 |
| I15 | Result · pager, *Download the parts that loaded*, *Download the N rows that failed*, *Roll back this run*, *Go to Parts →* | the same | 42 |
| I16 | *Cancel*, *← Back*, *Transform →*, *Validate →*, *Load →* | the same | 38–41 |

### 5.6 Templates (6·1–6·3), Rules (7·1–7·2), Performance (8·1)

| # | Today | New home | Image |
|---|---|---|---|
| TL1 | *New template* | the same | 43 |
| TL2 | Search *templates, job types…*, *All*, *+ Filter ▾*, ▦ | the same | 43 |
| TL3 | Row: name link, ✎, 👁 | the same | 43 |
| TL4 | Rows per page + ‹ › | pager | 43 |
| TD1 | *← Templates*, *Edit template*, *Duplicate*, *Deactivate*, *Delete* | the same | 44 |
| TD2 | Tabs Overview · Usage · Versions · Audit | the same; Overview shows every section with ✎ per section | 44–47 |
| B1 | Step rail (8) | the same | 48–55 |
| B2 | Details · pack cards ×4 | the same | 48 |
| B3 | Details · Name*, Service*, Job type, Any asset type, Skill needed, Crew size, Safety kit | the same | 48 |
| B4 | Details · *What the technician sees* ×4 ticks | the same | 48 |
| B5 | Safety · Must do, ↑ ↓ ×, *Add a safety check…*, *+ Add* | the same, the check text editable in place | 49 |
| B6 | Tasks · Photo required, Must do, ↑ ↓ ×, *Add a task…*, Minutes, *+ Add* | the same, task and minutes editable in place | 50 |
| B7 | Materials · ↑ ↓ ×, *Add a part…*, quantity, *+ Add* | the same, part and quantity editable in place | 51 |
| B8 | Readings · Photo required, Becomes a meter read, ↑ ↓ ×, Prompt, Unit, Min, Max, *+ Add* | the same, every cell editable in place | 52 |
| B9 | Help · Kind (*Document · Phone · Note*), What it is, Where to find it, ↑ ↓ ×, *+ Add* | Kind (*Document · Phone · Link*), What it is, a file / phone / https; editable in place | 53 |
| B10 | Signature · three ticks | the same (Keep) | 54 |
| B11 | Review · ✎ per section ×7 | *✎ Edit* on each section panel | 55 |
| B12 | *Save draft*, *Back*, *Continue*, *Publish template* | the same | 48–55 |
| R1 | Rules · Search *rules* (dead) | Search, wired | 56 |
| R2 | Rules · ▦ | ▦ | 56 |
| R3 | Rules · *Turn off* / *Turn on* per row | the same | 56 |
| R4 | Rules · Rows per page + ‹ › | pager | 56 |
| R5 | Builder · Rule name | Rule name* | 57 |
| R6 | Builder · Source module select | **Retired by the drawing** — the trigger names its process (*When this happens*); the source is derived | 57 |
| R7 | Builder · the trigger (one per source) | *When this happens* rows, *Add a trigger…*, *+ Add* | 57 |
| R8 | Builder · Template raised | **no drawn home** | — |
| R9 | Builder step 2 · Give the job to | Trigger step · *Give the job to* | 57 (58 retired) |
| R10 | Builder step 3 · *Tell the customer a visit is coming* | Notify · *Who hears* row (The job is raised · The customer · *A visit is coming*) | 59 |
| R11 | Builder step 4 · Escalate after (hours) | Notify · *When it stalls* rows (If · After · Also tell · Message) | 59 (60 retired) |
| R12 | Builder · *Back* / *Next* / *Activate rule* | *Back* / *Continue* / *Activate rule* | 57–61 |
| PF1 | Performance · ▦, rows per page + ‹ › | the same | 65 |

**Stored with no control today, and where each lands:**

| # | Stored / newly ruled | Home | Image |
|---|---|---|---|
| S1 | `work_order_templates.scope` (`per_premise · per_unit · per_asset`), never asked | **not drawn on 48**; the template summary's *Done to* (44, 55) shows it | 44, 55 |
| S2 | a template version's `change_note`, accepted by publish, never sent | **not drawn** | — |
| S3 | a task's instruction text (PO answer 3, 2026-10-04; a new column) | **not drawn** | — |
| S4 | a contractor's phone and email (P3.53, new columns) | Add a contractor · Phone, Email | 30 |
| S5 | a hold's reason and expected return (P0.3, new) | Put on hold · Reason*, Back on | 10 |
| S6 | a reassignment's reason (P4.4, new) | Reassign · *Why it moves* | 13 |

### 5.7 Count, and every item with no home

**Controls on today's screens: 115** (Orders 14 · one order 8 · edit page 10 · raise and its doors 11 · Approvals
and Map 5 · Crews and one technician 8 · Parts and Add part 12 · Import parts 16 · Templates and the builder 18 · Rules
and the rule builder 12 · Performance 1 — one row of §5.1–5.6 is one control or one family of identical controls).
**Homed 104 · retired by a ruling 5** (D2 *Mark complete*, D7 and D8 the office's checklist ticks — ruling 18; N6 Area
on the raise — ruling 24; R6 Source module — the 26 Sep trigger shape) **· no drawn home 6** (O8, O9, N4, AP3, C2,
R8). The two retired rule *steps* (58, 60) are not lost: their one control each moves to the Trigger and Notify steps
(R9, R11). **Stored or newly ruled with no control today: 6** — 3 land on a drawn control (S4–S6), 1 is shown on a
drawn summary and needs its control placed (S1), 2 have no drawing (S2, S3).

| Item | What we do (our judgment, law 13; decision log row *"CR-168 ROUND 1 · THE WORK FIELD MAP"*) |
|---|---|
| **O8** Reschedule selected… | Kept in the bulk bar beside *Assign selected…*; its dialog takes the drawn controls of 02's *Date* and *Window* (a date picker and the window list), never free text (`DEF-WRK-9570`). Image 02 draws Assign only because it is the assign state. |
| **O9** Change priority… | Kept in the bulk bar; one Priority select from the tenant's priorities. |
| **N4** the utility's own fields on a raise (CR-161 W4) | Kept on step 1, under Description, exactly as CR-161 placed them; not drawn because the demo tenant defines none. |
| **AP3 / C2** ▦ on Approvals and Crews | Kept — every list is the kit's table and ▦ comes with it; the drawings omit it, they do not remove it. |
| **R8** Template raised (rule builder) | On the Trigger step, under Rule name: *Raises* — Template* and Priority — the facts 56 and 62 show (*Raises Meter exchange — residential at Low priority*). |
| **S1** template scope | Asked on the builder's Details step as *Done to* (Premises · Unit · Asset), the label 44 and 55 already use; shown as a list column on 43 (P3.12). |
| **S2** change note | A *What changed* box on Review, required only when publishing a new version of a published template (P3.15). |
| **S3** task instruction text (PO answer 3) | A second line under each task on the builder's Tasks step (50), shown under the task on the order's checklist table (05, 06) and on the phone. |
| **B9** Help kind *Note* | **Kept as a fourth kind** beside Document · Phone · Link: rows of that kind may exist on live templates, and dropping the kind would strand them. |
| **R6** Source module | Derived from the trigger's process (`GET /work/rules/processes` serves `source_label`, §7.3), shown on the list (56) and the rule's page; not asked. |

### 5.8 · The 7 phases and 164 tasks (the blueprint's §02) — every TODAY re-validated on `2.490.6`

Ids, kinds and titles are the blueprint's; each row's full text (what it involves, reference, outcome) is in
`blueprint.html`. **The rounds are §8.** *Today* says whether the blueprint's TODAY (written on `2.340.0`) still holds:
**still needed** · **partly done** (some of it landed since) · **done since** · **changed** (true in part, or the fact
moved) · **stated** (the row records an absence or a process step and is still accurate). The 75 front-end rows were
re-measured in the browser by lane WORK-CR (evidence = a photograph in `08-qa/work-2026-10-04/before/` or a defect);
the 89 others by lane WORK-SRV in §7.1, whose word is copied here (TRUE → still needed).

### P0 · Foundations — 7 tasks

| Task | Kind | What | Today on `2.490.6` | Evidence |
|---|---|---|---|---|
| P0.1 | DB | Seed priorities on existing orders | still needed | §7.1: TRUE |
| P0.2 | DB | work_orders acceptance columns | still needed | §7.1: TRUE |
| P0.3 | DB | Hold reason and expected return | still needed | §7.1: TRUE |
| P0.4 | Settings | Hold-reason lookup | still needed | §7.1: TRUE |
| P0.5 | Test | Migration guard | stated | §7.1: STATED |
| P0.6 | E2E | No new journey | stated | §7.1: STATED ×2 |
| P0.7 | Other module | None | stated | §7.1: STATED ×2 |

### P1 · Stop losing work — 36 tasks

| Task | Kind | What | Today on `2.490.6` | Evidence |
|---|---|---|---|---|
| P1.1 | Front end | onError on three mutations, catch on the bulk path | still needed | edit save and cancel carry no onError; a crew pick 404s silently (`DEF-WRK-9563`); Reschedule shows nothing (`b11-reschedule-garbage`) |
| P1.2 | Front end | Customer, meter, unit and window on the order | still needed | Overview has no meter, unit, customer or window (`a03-order-overview`, `DEF-WRK-9581`) |
| P1.3 | Front end | The crew control on 1·3 | still needed | Assigned to is a plain select; no crew control with advice (`a12-edit-unassigned`) |
| P1.4 | Front end | Real date and time controls | partly done | the edit page's Date is a real date box; bulk Reschedule is still three free-text boxes (`DEF-WRK-9570`) |
| P1.5 | Front end | The approvals row action opens the ORDER | still needed | eye opens the premises' build tab (`b18c-approvals-eye-destination`, `DEF-WRK-9575`) |
| P1.6 | Backend | An accepted order stays findable | still needed | §7.1: TRUE |
| P1.7 | Front end | Release two held controls on 2·1 | still needed | *Open work orders* still held (`a21-approvals`) |
| P1.8 | Test | A refused save is visible | stated | §7.1: STATED |
| P1.9 | E2E | journeys/dispatcher-reassigns.md | changed | §7.1: CHANGED |
| P1.10 | Other module | identity — nothing | stated | §7.1: STATED ×2 |
| P1.11 | DB | None — and that is the finding | changed | §7.1: CHANGED |
| P1.12 | Settings | None | stated | §7.1: STATED ×2 |
| P1.13 | Front end | Rename the tab to Approvals | still needed | tab and title read *Awaiting approval* (`a01-orders-list`) |
| P1.14 | Other | Tell beta #27 where the materials are | stated | §7.1: STATED |
| P1.15 | Backend | The customer's name and phone reach the job | still needed | §7.1: TRUE |
| P1.16 | Front end | Dates in the order's history read as dates | still needed | raw ISO timestamps (`a03-order-audit`, `DEF-WRK-9584`) |
| P1.17 | Front end | The history says who acted, and on whom | still needed | Who names the technician for the dispatcher's act (`DEF-WRK-9584`) |
| P1.18 | Front end | Numbers without four trailing zeros | still needed | `1.0000 roll`, `18.0000–96.0000`, builder quantity `1.0000` (`a03-order-parts`, `a51-materials`) |
| P1.19 | Front end | The service by its name | still needed | Service reads lower-case *water* (`a03-order-overview`) |
| P1.20 | Front end | Cancel's other button says Keep the order | still needed | the dialog's other button reads *Cancel* (`a11-cancel-dialog`) |
| P1.21 | Front end | Location and customer on the Overview — two tabs go | still needed | six tabs (`a03-order-location`, `a03-order-customer`) |
| P1.22 | Front end | See the photographs | still needed | no photo viewer on the office page |
| P1.23 | Backend | Serve the signature's mark | still needed | §7.1: TRUE |
| P1.24 | Front end | The signature on the Overview, viewable | still needed | no signature panel (`a04-order-completed-overview`) |
| P1.25 | Backend | The edit page opens with the truth | still needed | §7.1: TRUE |
| P1.26 | Front end | Change effects says what this save will do | still needed | Change effects shows the same three lines whatever changed (`a12-edit-unassigned`) |
| P1.27 | Front end | Assign… on a job nobody has | still needed | no *Assign…* on an unassigned job's head (`a10-put-on-hold`, WO-0029) |
| P1.28 | Front end | Tasks as a table | still needed | tasks a list (`a03-order-checklist`) |
| P1.29 | Front end | The order page has two shapes | still needed | one shape; a completed job keeps the open job's head (`a04-order-completed-overview`) |
| P1.30 | Front end | Page actions top right | partly done | the order page's actions top right since `2.445.13`; the edit page's buttons and the list's create are still at the bottom (`a12-edit-unassigned`, `a01-orders-list`) |
| P1.31 | Backend | Closing a job moves it to Complete | still needed | §7.1: TRUE |
| P1.32 | Front end | Accept on the order page | still needed | no Accept on the order page (`a04-order-completed-overview`) |
| P1.33 | Backend | A reading that is words can be recorded | still needed | §7.1: TRUE |
| P1.34 | Backend | The office never completes a job | still needed | §7.1: TRUE (+1 door) |
| P1.35 | Front end | The current step can be read | still needed | pills *Scheduled · Completed* contradict each other (`a04-order-completed-overview`) |
| P1.36 | Front end | Accept on the approvals row | still needed | no ✓ on the approvals row (`a21b-approvals-one-row`) |

### P2 · Raise a job — 21 tasks

| Task | Kind | What | Today on `2.490.6` | Evidence |
|---|---|---|---|---|
| P2.1 | Front end | The create moves to the header and goes accent | still needed | create outlined under the pager (`DEF-WRK-9562`) |
| P2.2 | Front end | The raise form — five fields | still needed | free-text Premises and Job type (`a14-raise-1`, `DEF-WRK-9572`) |
| P2.3 | Front end | Job type as a two-level picker | still needed | flat type list everywhere (`b12-filter-menu`, `DEF-WRK-9582`) |
| P2.4 | Front end | Raise from an account — the form arrives filled | partly done | a door exists — the account's *⚡ Raise work here* — and opens the blank wizard (`b22b-account-work-tab`, `DEF-WRK-4752`); the drawn address is not routed (`a19-account-raise`) |
| P2.5 | Backend | Assign at creation | still needed | §7.1: TRUE |
| P2.6 | Test | The raise path on PostgreSQL | stated | §7.1: STATED ×2 |
| P2.7 | E2E | journeys/raise-a-job.md | stated | §7.1: STATED ×2 |
| P2.8 | Other module | customers — nothing | stated | §7.1: STATED ×2 |
| P2.9 | DB | None | still needed | §7.1: TRUE |
| P2.10 | Settings | None | stated | §7.1: STATED ×2 |
| P2.11 | Backend | A template's service must match the job's meter | still needed | §7.1: TRUE |
| P2.12 | Backend | Raise many jobs in one press | still needed | §7.1: TRUE |
| P2.13 | Backend | A unit must be in the job's building | still needed | §7.1: TRUE |
| P2.14 | Backend | The template's scope, service and asset type reach the job | still needed | §7.1: TRUE |
| P2.15 | Front end | Units on the raise form | still needed | no units table (`a14-raise-1`) |
| P2.16 | Front end | Asset type, then the asset | still needed | no asset type or asset table |
| P2.17 | Backend | The job's area is its building's | still needed | §7.1: TRUE |
| P2.18 | Front end | Assign on the raise — or leave it blank | still needed | step 2 is Due + Area (`a16-raise-step2`) |
| P2.19 | Front end | Raise from an asset — the same raise, filled | partly done | a one-page raise exists on the asset (`a20-asset-raise`); ruling 35 replaces it with the filled 1·4f |
| P2.20 | Backend | A job raised on an asset says where it is | still needed | §7.1: TRUE |
| P2.21 | Backend | An asset is offered its own service's templates | still needed | §7.1: TRUE |

### P3 · Open the doors — 67 tasks

| Task | Kind | What | Today on `2.490.6` | Evidence |
|---|---|---|---|---|
| P3.1 | Front end | Cluster the map pins | **built 2026-10-04 (`2.498.0`, lane MAP2)** — 17 orders on 5 places draw as 5 marks with counts, every order reachable by mouse and keyboard (`DEF-WRK-9598`); a key (`DEF-WRK-9599`) | §13 |
| P3.2 | Front end | A pin opens the order | **built 2026-10-04 (`2.498.0`, lane MAP2)** — a pin, and every job in a cluster's list, opens `/work/orders/{id}` (`DEF-WRK-9576`) | §13 |
| P3.3 | Other | ⚠ A tile source | **built 2026-10-04 (`2.494.0`)** — Esri street tiles through the shared basemap module (`OQ-WRK-12787` CLOSED, lane W-MAP); ⚠ the browser refuses the tiles on every build until `DEF-INT-7430` (the baked page-security policy) is fixed — `08-qa/work-2026-10-04/after/W-MAP-network-log.json` | §7.1: closed |
| P3.4 | Backend | Crews page in SQL | still needed | §7.1: TRUE (+cap) |
| P3.5 | Backend | Templates footer counts in SQL | still needed | §7.1: TRUE |
| P3.6 | Front end | Select all across pages | still needed | ticks are per page only |
| P3.7 | Front end | Accept in bulk | still needed | no accept at all on the queue |
| P3.8 | Front end | Edit a part | still needed | no row action (`a35-parts`, `DEF-WRK-9578`) |
| P3.9 | Front end | Part active / inactive | still needed | `DEF-WRK-9579` |
| P3.10 | Front end | Filters on the parts list | still needed | `DEF-WRK-9580` |
| P3.11 | Front end | Release the Issue log | still needed | Issue log held (`a35-parts`, `DEF-WRK-9574`) |
| P3.12 | Front end | Scope on the template wizard and list | still needed | no scope on the builder or the list (`a48-builder-details-filled`, `DEF-WRK-9577`) |
| P3.13 | Front end | Edit rows in place, in all five builder steps | still needed | rows plain text in five steps (`a49`–`a53`, `DEF-WRK-9565`, `9566`) |
| P3.14 | Backend | Hold a help document | still needed | §7.1: TRUE |
| P3.15 | Front end | Ask for a change note on publish | still needed | `publishTemplate(id, null)` (`DEF-WRK-9568`) |
| P3.16 | Front end | A permanent New rule action | still needed | no *+ New rule* with rules on screen (`a56-rules`, `DEF-WRK-9564`) |
| P3.17 | Front end | Edit a rule | still needed | no edit on a rule |
| P3.18 | Front end | Wire the rules search | still needed | search dead (`b15-rules-search`, `DEF-WRK-9573`) |
| P3.19 | Front end | ⚠ Rule builder onto the shared WizardFrame and the kit | still needed | hand-rolled five-step rail (`a57-rule-step1`, `DEF-WRK-5066`) |
| P3.20 | Test | A door test per released control | stated | §7.1: STATED ×2 |
| P3.21 | E2E | journeys/supervisor-writes-a-rule.md | stated | §7.1: STATED ×2 |
| P3.22 | Other module | assets — the page behind the asset's button | still needed | §7.1: TRUE |
| P3.23 | DB | Index for server paging | still needed | §7.1: TRUE |
| P3.24 | Settings | None | stated | §7.1: STATED |
| P3.25 | Front end | A Link kind — video and web pages | still needed | kinds Document · Phone · Note (`a53-help`, `DEF-WRK-9567`) |
| P3.26 | Front end | One template summary — on Review and on Overview | still needed | Review is a count table, Overview a count list (`a55-review`, `a44-template-overview`) |
| P3.27 | Front end | Add a crew | still needed | no Add a crew |
| P3.28 | Backend | A template's change history | still needed | §7.1: TRUE |
| P3.29 | Front end | Usage counts in words | still needed | *0 orders raised across 2 versions* (`a44-template-usage`) |
| P3.30 | Front end | Every process in the rule form | still needed | Source module select + one trigger per source (`a57-rule-step1`) |
| P3.31 | Backend | Stamp the label the order table accepts — DEF-WRK-4096 | changed | §7.1: CHANGED |
| P3.32 | Backend | Two new overnight readers | still needed | §7.1: TRUE |
| P3.33 | Backend | Continuous flow takes a service and a unit | still needed | §7.1: TRUE |
| P3.34 | Backend | Six screen moments tick the rule's job | still needed | §7.1: TRUE |
| P3.35 | Backend | A rule shapes the failed-job retry | still needed | §7.1: TRUE |
| P3.36 | Backend | Read steps 2 and 4 — today nothing does | still needed | §7.1: TRUE |
| P3.37 | Front end | Step 3 shows Notification settings — no second copy | still needed | step 3 is one tick of its own |
| P3.38 | Backend | One subject, one open job per template | still needed | §7.1: TRUE |
| P3.39 | Front end | The Review states tonight's count | still needed | Review states no count |
| P3.40 | Test | Each process raises on PostgreSQL — red first | stated | §7.1: STATED |
| P3.41 | DB | None — and it is worth saying why | changed | §7.1: CHANGED |
| P3.42 | Other module | customers and metering — six screens read the pre-selection | still needed | §7.1: TRUE |
| P3.43 | Front end | Add crew member on the Crews page | still needed | no door (`a25-crews`) |
| P3.44 | Backend | Move a technician to another crew | still needed | §7.1: TRUE |
| P3.45 | Front end | A technician's Jobs tab | still needed | `?tab=jobs` falls back to Overview |
| P3.46 | Backend | A technician's figures | still needed | §7.1: TRUE |
| P3.47 | Backend | A job's estimate is its template's minutes | still needed | §7.1: TRUE |
| P3.48 | Front end | Certifications as a table, with add and renew | still needed | a line of names (`a31-tech-certifications`) |
| P3.49 | Front end | Crews as three lists | still needed | one table of seven mixed rows (`a25-crews`) |
| P3.50 | Front end | The Add part form speaks plainly | still needed | library English (`a37-add-part-empty`, `DEF-WRK-9585`) |
| P3.51 | Other module | No library English reaches a clerk | stated | §7.1: STATED |
| P3.52 | Backend | A crew's skills can be set | still needed | §7.1: TRUE |
| P3.53 | DB | A contractor's phone and email | still needed | §7.1: TRUE |
| P3.54 | Front end | The part's Name | still needed | *Description* (`a36-add-part`) |
| P3.55 | Backend | The parts import keeps the category | still needed | §7.1: TRUE (unverified) — **verified by WORK-CR on a real file:** *Meters* in the file, category *null* on MTR-W34 after the load (`a40-import-validate`, `DEF-WRK-9587`) |
| P3.56 | Front end | The parts import speaks about parts | still needed | *Every part needs a description.*, *…on every premises.*, 0 rows forward, blank Key (`a39`–`a42`, `DEF-WRK-9588`) |
| P3.57 | Backend | The seven escalations fire | still needed | §7.1: TRUE |
| P3.58 | Other module | Six escalation messages in Notifications | still needed | §7.1: TRUE |
| P3.59 | Other module | Reminders live in Notifications | still needed | §7.1: TRUE |
| P3.60 | Front end | A create in the header, and a search that searches | still needed | Rules: no create in the head, dead search (`a56-rules`) |
| P3.61 | Backend | Last fired and Jobs raised | changed | §7.1: CHANGED |
| P3.62 | Front end | The rule detail view, and its route | still needed | not routed (`a62-rule-detail`) |
| P3.63 | Front end | Open, edit and duplicate on a rule row | still needed | no row actions (`a56-rules`) |
| P3.64 | Front end | The builder becomes three steps | still needed | five steps (`a57-rule-step1`) |
| P3.65 | Backend | Several triggers on one rule | still needed | §7.1: TRUE |
| P3.66 | Front end | The notifications table | still needed | no notifications table |
| P3.67 | Front end | Escalations become rows you add | still needed | one *Escalate after (hours)* box (`a57-rule-step4`) |

### P4 · Know where it is — 14 tasks

| Task | Kind | What | Today on `2.490.6` | Evidence |
|---|---|---|---|---|
| P4.1 | Front end | Technician acceptance on 1·1 and 1·2 | still needed | no acceptance shown anywhere |
| P4.2 | Front end | The status timeline | still needed | no timeline |
| P4.3 | Front end | Hold reason and resume | still needed | hold has no dialog and no resume (`a10-put-on-hold`) |
| P4.4 | Backend | Reassign as one act with a reason | still needed | §7.1: TRUE |
| P4.5 | Backend | ⚠ The match ADVISES and never blocks | still needed | §7.1: TRUE |
| P4.6 | Test | 🔒 The override is audited | still needed | §7.1: TRUE |
| P4.7 | Other module | work (field app) — acceptance | stated | §7.1: STATED ×2 |
| P4.8 | DB | The acceptance columns land here if P0.2 slipped | still needed | §7.1: TRUE |
| P4.9 | E2E | journeys/technician-accepts.md | stated | §7.1: STATED ×2 |
| P4.10 | Settings | None | stated | §7.1: STATED |
| P4.11 | Backend | Hold, cancel, completion and acceptance in the order's history | still needed | §7.1: TRUE |
| P4.12 | Front end | Advice beside every name when assigning | still needed | no advice beside names (`a12-edit-unassigned`) |
| P4.13 | Front end | Bulk assign asks who, when, and says how many | still needed | bulk Assign asks who only (`a02-bulk-assign`) |
| P4.14 | Backend | Send a completed job back to the field | still needed | §7.1: TRUE |

### P5 · Protect the promise — 11 tasks

| Task | Kind | What | Today on `2.490.6` | Evidence |
|---|---|---|---|---|
| P5.1 | Front end | The SLA headline agrees with its rows | still needed | *SLA met 100.0%* over 0.0% rows (`a65-performance`, `DEF-WRK-9586`); PO answer (1) sets the 72 h default |
| P5.2 | Backend | Pause the SLA clock on hold | still needed | §7.1: TRUE ×2 |
| P5.3 | Front end | The at-risk board | still needed | no at-risk board |
| P5.4 | Front end | The schedule board | still needed | no schedule board |
| P5.5 | Front end | Bulk raise across buildings | still needed | no bulk raise |
| P5.6 | Backend | Performance paging | still needed | §7.1: TRUE |
| P5.7 | E2E | journeys/sla-breach.md | stated | §7.1: STATED |
| P5.8 | DB | SLA pause columns | still needed | §7.1: TRUE ×2 |
| P5.9 | Test | The weighted SLA figure | changed | §7.1: CHANGED |
| P5.10 | Settings | SLA per job type | still needed | §7.1: TRUE |
| P5.11 | Other module | None | stated | §7.1: STATED |

### P6 · Tell people — 8 tasks

| Task | Kind | What | Today on `2.490.6` | Evidence |
|---|---|---|---|---|
| P6.1 | Backend | Tell the consumer | changed | §7.1: CHANGED |
| P6.2 | Backend | Tell the back office | still needed | §7.1: TRUE |
| P6.3 | Backend | ⚠ Print a work order | still needed | §7.1: TRUE |
| P6.4 | Settings | Notification rules | changed | §7.1: CHANGED |
| P6.5 | Other module | notifications — four new message kinds | changed | §7.1: CHANGED |
| P6.6 | Test | No message without a rule | stated | §7.1: STATED |
| P6.7 | DB | Notification rule rows | changed | §7.1: CHANGED |
| P6.8 | E2E | journeys/customer-told-about-a-visit.md | stated | §7.1: STATED |

**Count:** 164 tasks — P0 7 · P1 36 · P2 21 · P3 67 · P4 14 · P5 11 · P6 8.
**Re-validated:** **still needed 127** (front end 71 · other 56) · **partly done 4** (P1.4 date controls, P1.30 actions
top right, P2.4 the account door, P2.19 the asset door — all front end) · **changed 10** (all server-side, §7.1) ·
**done since 0** · **stated 23**. Nothing the blueprint found on `2.340.0` has been fixed since.
**The PO's three answers of 2026-10-04 move three rows:** P5.1/P5.9 measure an undated job against the Normal
priority's 72 h; P4.5's certification half becomes warn-only (`BR-WRK-030` superseded); P3.13 gains the task
instruction text (a new column, §7.3 `work/0028`).

## 6 · The 34 beta observations (blueprint §04 J1), reproduced on `2.490.6` and filed

**How:** the same build, database and walk as §4; each observation was tried in the browser BEFORE any code was read,
then filed with `10-scripts/file_defect.py --id-module WRK` (filed first, fixed later — maintenance process). The
register was searched first and an existing row is referenced, never duplicated. A *change request* in the
blueprint's classification is carried by this CR's tasks and is not filed; *correct by design* is recorded and left.

| # | Reported (short) | On `2.490.6` | Defect | Evidence |
|---|---|---|---|---|
| 1 | Map shows dots on a blank canvas | **Reproduced** — no ground layer; the tile source waited on the PO (`OQ-WRK-12787`, CLOSED 2026-10-04: Esri). **Fixed P3.3** — the street ground is drawn | `DEF-WRK-9561` | `a24-map` |
| 2 | *+ New work order* at the bottom | **Reproduced** — outlined, under the pager (`DEF-WRK-4105`, open, says there is no button at all; it is stale since `DEF-WRK-4121`) | `DEF-WRK-9562` | `a01-orders-list`, `b11-reschedule-garbage` |
| 3 | Two clear crosses in the search box | **Reproduced** on Orders and Rules — the kit's ✕ beside Chromium's own | `DEF-SHL-5345` (open; every `DataTable`) — referenced | `b03-search-clear`, `b15-rules-search` |
| 4 | Edit / assign fails silently | **Reproduced, sharper:** a crew or contractor picked on the edit page is posted as `technician_id`, the server answers 404 and the page says nothing (a person saves fine) | `DEF-WRK-9563` (critical) | `b04-edit-save-Field-crew-A-`, `b04-edit-save-Redline-Meter-Services`, `b04-edit-save-D-Ortiz` |
| 5 | Rules unclear | **Reproduced** — no *+ New rule* with rules on screen, no way to open or edit a rule; the explanation half is a change (rule 33: a clearer shape, not more prose) | `DEF-WRK-9564` | `a56-rules` |
| 6 | Builder Tasks rows cannot be edited | **Reproduced** | `DEF-WRK-9565` | `a50-tasks` |
| 7 | Builder Materials rows cannot be edited | **Reproduced**, and the same in Safety, Readings and Help (ruling 5) | `DEF-WRK-9566` | `a49-safety`, `a51-materials`, `a52-readings` |
| 8 | Help *Document* has no upload | **Reproduced** — kinds *Document · Phone · Note*, a typed *Where to find it*, no Link | `DEF-WRK-9567` | `a53-help` |
| 9 | Versions *What changed* blank | **Reproduced** at the source (`TemplateBuilder.tsx:1433` publishes with `null`); Review has no note box. The demo's seeded versions carry notes, so the tab looks right until a clerk publishes | `DEF-WRK-9568` | `a55-review`, `a44-template-versions` |
| 10 | An approved order gets lost | **Reproduced** — after acceptance WO-0037 is on neither Orders (*No results for 'WO-0037'*) nor Approvals; opened by its address it still reads *Scheduled* with *Mark complete* live | `DEF-WRK-9569` (critical); server half `DEF-WRK-9526` | `b10-accepted-order-searched` |
| 11 | Reschedule takes `UU898` / `99989` | **Reproduced** — three `type=text` boxes; the press shows no message | `DEF-WRK-9570` | `b11-reschedule-garbage` |
| 12 | *Filter not working* | **Not a broken filter** — the five chips work; **no demo order carries a priority** (0 of 40), so *Priority* returns nothing and reads as broken | `DEF-WRK-9571` (data) | `b12-filter-menu` |
| 13 | Duplicate gives a Draft | **Correct by design** (`US-WRK-015` TC-7) — not filed | — | — |
| 14 | Create WO fields should be dropdowns | **Reproduced** — Premises and Job type are free-text boxes | `DEF-WRK-9572` | `a14-raise-1`, `b16a-raise-continue-empty` |
| 15 | Rules search not working | **Reproduced** — *Leak* leaves all seven rows | `DEF-WRK-9573` | `b15-rules-search` |
| 16 | How can a job raise from address + sub-area? | **Change** — carried by P2.2 (the five-field raise); the free-text form is `DEF-WRK-9572` | — | `a14-raise-1` |
| 17 | *Register buttons* use case | **Reproduced** as the blueprint guessed — *Issue log* is still held over a live endpoint (`DEF-WRK-3646` records only its tooltip half) | `DEF-WRK-9574` | `a35-parts` |
| 18 | Approvals 👁 opens the premises | **Reproduced** — `/premises/…?tab=build` | `DEF-WRK-9575` | `b18c-approvals-eye-destination` |
| 19 | A map pin should open the order | **Reproduced** — it opens the order's EDIT page | `DEF-WRK-9576` | `b19-map-pin-click` |
| 20 | No service / purpose on a template | **Reproduced** as corrected on 24 Sep — Service is asked; *what it is done to* (scope) is never asked nor shown | `DEF-WRK-9577`; server half `DEF-WRK-9528` | `a48-builder-details-filled`, `a43-templates` |
| 21 | Assign while creating | **Change** — P2.5 / P2.18 | — | `a16-raise-step2` |
| 22 | Raise from the account | **Partly no longer reproduces:** the account's Work tab now has *⚡ Raise work here*; it opens the blank wizard (`DEF-WRK-4752`, open — referenced) and the drawn address is not routed | `DEF-WRK-4752` — referenced | `b22b-account-work-tab`, `a19-account-raise` |
| 23 | Raise from the asset | **Does not reproduce** — *Raise work order* sits on the asset page (`b23a-asset-page`); ruling 35 changes its shape (a change, not a defect) | — | `b23a-asset-page`, `a20-asset-raise` |
| 24 | No edit part | **Reproduced** | `DEF-WRK-9578` | `a35-parts` |
| 25 | No active / inactive part | **Reproduced** | `DEF-WRK-9579` | `a35-parts` |
| 26 | No filters on parts | **Reproduced** | `DEF-WRK-9580` | `a35-parts` |
| 27 | Photos / readings / materials only on the checklist | **No longer reproduces as a missing panel:** the Parts tab lists planned and used, the Checklist's readings table has Value and Photograph columns — empty because the demo has no field evidence (`a03-order-parts`, `a03-order-checklist`). Seeing photographs and the signature is ruling 12 (P1.22, P1.24) | — | `a03-order-parts`, `a03-order-checklist` |
| 28 | Duplicate on orders and rules | **Change** — P3.63 | — | — |
| 29 | Select all | **Change** — P3.6 | — | — |
| 30 | Consumer info missing | **Reproduced** — Customer tab reads *Account —* | `DEF-WRK-9529` (WORK-SRV) — referenced | `a03-order-customer` |
| 31 | Asset / unit not shown | **Reproduced** | `DEF-WRK-9581` | `a03-order-overview` |
| 32 | Type and sub-type one list | **Reproduced** — *Electrical Line, Outage report, Transformer fault, Voltage complaint* flat among headings | `DEF-WRK-9582` | `b12-filter-menu` |
| 33 | An invited technician cannot set a password / log in | **Reproduced, and wider than reported:** a login scoped to the field app can **never** sign in — `POST /auth/session` passes no surface, so `services.sign_in` treats every attempt as the web and refuses (`403 AUTH-002 identity.signIn.fieldAppOnly`), from the field app too; the web form shows *That email or password is incorrect.* | `DEF-WRK-9583` (critical) | `b33a-technician-first-signin` |
| 34 | Raise form: Job Type*, Template*, Priority, Expected Date, Description | **Change** — P2.2 (ruling 23 folds *Expected Date* into the due date) | — | `a14-raise-1` |

**Count (34):** **reproduced 24** (22 filed new, 2 referenced: `DEF-SHL-5345`, `DEF-WRK-9529`; where WORK-SRV
filed the server half, the screen row cites it) · **not a broken control — the data 1** (#12, filed new as data,
`DEF-WRK-9571`) · **partly no longer reproduces 1** (#22, `DEF-WRK-4752` referenced) · **no longer reproduces 2**
(#23, #27) · **change, carried by this CR 5** (#16, #21, #28, #29, #34) · **correct by design 1** (#13).

**Found on the walk beyond the beta, filed:** `DEF-WRK-9584` (Audit dates and *Who*), `DEF-WRK-9585` (Add part speaks
library English), `DEF-WRK-9586` (*SLA met 100.0%* over 0.0% rows), `DEF-WRK-9587` (Import parts drops the category),
`DEF-WRK-9588` (Import parts' counts and words). **Seen and referenced, not re-filed** (WORK-SRV's rows): the office
completing a job — the screen half proved here, the office ticked WO-0037's whole checklist and closed it with 0 of 3
required photos (`DEF-WRK-9525`, `b18a-office-ticked-checklist`); the edit page opening an assigned job on *Nobody yet*
(`DEF-WRK-9530`, `a13-edit-assigned`); a hold missing from the Audit tab (`DEF-WRK-9532`).

**Defects this lane filed: 28** — `DEF-WRK-9561`–`9583` from the beta (23) and `9584`–`9588` from the walk (5); three critical (`9563`, `9569`, `9583`).
They were first allocated as `9525`–`9555` and renumbered before the push, because WORK-SRV pushed `9525`–`9533` from
its own worktree while this lane filed (law 11's allocator collision: both computed *max + 1* correctly from worlds
that could not see each other); three of the first 31 were dropped as duplicates of WORK-SRV's rows (`9525`, `9529`,
`9530`).

## 7 Server answers and the API contract — WORK-SRV

*(Owned by lane WORK-SRV. Written as its own file because `CR-168-BRC10-work-backoffice-redesign.md`
carried no §7 placeholder at tip `9787009ee` when this was ready; the coordinator or lane WORK-CR
moves it into the CR as §7 verbatim. Nothing here is built.)* Round 1, 2026-10-04. Read only, except
ten HELD test cases that prove nine defects (§7.3). Line numbers at tip `9787009ee` (`2.492.0`).

**Where it was measured.** Code read at the tip; data measured on PostgreSQL 16 (`sbh_worksrv`,
`migrate` + `seed_demo` + `load_sample_data --tenant brazosbend`, the demo tenant the 65 images were
captured on). The blueprint's TODAY column was written on `2.340.0`.

**PO answers that arrived during this round and are built INTO this contract, not asked again**
(decision log 2026-10-04, *"THREE WORK ANSWERS"*): (1) a job with no due date and no priority is
measured against a DEFAULT target — the Normal priority's hours (72 h seeded), a tenant setting —
and counts in *SLA met*; (2) a lapsed certification WARNS and never blocks, every tenant
(`BR-WRK-030` SUPERSEDED); (3) every template task carries an instruction text, edited on the
builder's Tasks step and shown on the checklist. (4) The map tile source waits for the PO's details
— minted as **`OQ-WRK-12787`** (§7.6), the only question this round raises.

---

## 7.1 · The blueprint's TODAY, re-measured — every backend, DB, settings, test, E2E and other-module task

89 of the 164 tasks are not front-end. Status: **TRUE** = still true at the tip · **CHANGED** = true
in part, or the fact moved (file:line) · **DONE** = fixed since `2.340.0` · **STATED** = the row
states an absence or a process step and is still accurate.

| Task | Blueprint's claim (short) | At the tip | Status |
|---|---|---|---|
| P0.1 | 0 of 39 orders carry a priority | **0 of 40** carry `priority_id`; 3 of 40 carry `due_at` (demo DB). The four priorities exist (URGENT 4 h · HIGH 8 h · NORMAL 72 h · LOW 168 h) | TRUE |
| P0.2 | acceptance columns; `accepted_by` is the SUPERVISOR | No `accepted_by_technician` / `accepted_at_technician` / `declined_reason`; `accepted_by` + `accepted_at` are the office acceptance (`metering/connections.py:1216`, `:1224`) | TRUE |
| P0.3 | hold reason + expected return; a CHECK makes a new value a migration | No column; `set_dispatch_state` writes `dispatch_state` alone (`work/dispatch.py:1083`). Decided: a tenant LOOKUP FK, no CHECK (J1) | TRUE |
| P0.4 | hold-reason lookup | None exists | TRUE |
| P0.5 | migration guard, up and down on PG | — (process; applies to every migration in §7.5) | STATED |
| P0.6 / P0.7 | no journey; no other module | Still accurate | STATED ×2 |
| P1.6 | an accepted order stays findable | `GET /work-orders` lists `state ∈ planned·in_progress·blocked` only (`work/seams/metering_seam.py:159`); 23 completed demo jobs are reachable only by number | TRUE |
| P1.8 | a refused save is visible (test, red first) | — (front-end test) | STATED |
| P1.9 | extend `dispatcher-reassigns.md` | No such journey file exists in `08-qa/01-e2e/journeys/` (only `J63`, `J64` touch Work) — it is CREATED, not extended | CHANGED |
| P1.10 / P1.12 | identity nothing; settings none | Accurate | STATED ×2 |
| P1.11 | P1 needs no migration | **No longer true:** P1.33 needs a text column — `work_order_readings.value` is `NUMERIC(18,4)` (`work/models.py:1961`) | CHANGED |
| P1.14 | tell beta #27 where the materials are | Not a server item | STATED |
| P1.15 | the customer's name and phone never reach the job | `customers_seam.account()` serves id, number, status, unit (`work/seams/customers_seam.py:42-51`); `mobile._customer_contact` reads `name`/`phone` from it (`work/mobile.py:345-346`) → always `None`. Demo: **0 of 40** jobs name an account (was 1 of 43). **`DEF-WRK-9529`** | TRUE |
| P1.23 | serve the signature's mark | `signature_for_order` returns name, time, refused, no link, no `captured_by` (`work/evidence.py:693-706`) | TRUE |
| P1.25 | the edit page opens with the wrong technician, date and time | `form_values` sends `technician = dispatch._holder(order)` — kind, name, slug, **no id** (`work/edit.py:193`). Date/time half is front end. **`DEF-WRK-9530`** | TRUE |
| P1.31 | a close never writes the dispatch status | `submit_field_result` writes `state` only (`metering/connections.py:7202-7217`). Demo: 23 completed → 22 `queued`, 1 `on_site`, **0 `complete`**. **`DEF-WRK-9526`** | TRUE |
| P1.33 | a reading that is words is refused | `_decimal_or_422` → `work.reading.value_not_a_number` (`work/evidence.py:111-120`) | TRUE |
| P1.34 | the server takes a completion from any role | `POST /work-orders/{id}/field-result` is `AnyTenantRole` (`metering/api.py:3116`, was `:3025`) and `submit_field_result` checks no actor (`metering/connections.py:7150`). **A second door the blueprint did not name:** `PATCH …/edit` accepts `dispatch_state=complete` (`work/edit.py:217-227`). **`DEF-WRK-9525`** | TRUE (+1 door) |
| P2.5 | assign at creation; `/candidates` needs the order | `create_work_order` takes no assignee; `assign_candidates(order_id)` (`work/dispatch.py:661`) | TRUE |
| P2.6 / P2.7 | raise path on PG; `raise-a-job.md` | — | STATED ×2 |
| P2.8 / P2.10 | customers nothing; settings none | Accurate | STATED ×2 |
| P2.9 | the five fields write existing columns | True for the fields; assignment at creation writes `work_order_assignments` rows, not a column | TRUE |
| P2.11 | a water template is accepted on an electric meter | Nothing compares template service with the anchor's service in `create_work_order` (`metering/connections.py:2634-2830`) | TRUE |
| P2.12 | raise many in one press | No bulk raise. `bulk_act`'s docstring still says *"`OQ-WRK-1497` … is OPEN"* (`work/dispatch.py:1205`) — it CLOSED 2026-09-04 (*"three separate assignments"*): a stale body, recorded here | TRUE |
| P2.13 | a unit of another building is accepted | The unit is compared with the CONNECTION's premises only (`metering/connections.py:~2700`, `work.order.unit_not_on_build`). **`DEF-WRK-9527`** | TRUE |
| P2.14 | template scope/service do not reach the job | `scope = data.get("scope") or SCOPE_PREMISE` (`metering/connections.py:~2684`). **`DEF-WRK-9528`** | TRUE |
| P2.17 | the Area chip filters a column nothing writes | `_apply_filters` filters `area_id` (`work/dispatch.py:211`). Demo: **79 of 79** premises carry an area, **0 of 40** orders | TRUE |
| P2.20 | a job raised on an asset stores the asset only | `create_work_order` fills nothing from `asset_id`; `selectors._premise_of` / `dispatch._premises_row_of` do not walk asset → service point → unit | TRUE |
| P2.21 | an asset is offered other services' templates | `templates_for_asset` filters by asset type only (`work/asset_door.py:179-224`), and is an unpaged Python loop with two seam calls per template | TRUE |
| P3.3 | a tile source | **`OQ-WRK-12787`** — CLOSED 2026-10-04, PO: *"use Esri"* | built (lane W-MAP) |
| P3.4 | Crews merged in Python, then sliced | `crews_page` builds every row, sorts and slices in Python (`work/workforce.py:146-238`). **And a hard cap rides on it:** `assign_candidates` takes ONE page of it (`per=MAX_PAGE_SIZE`, 200) as the whole list (`work/dispatch.py:681`). **`DEF-WRK-9531`** (NFR-5) | TRUE (+cap) |
| P3.5 | templates footer counted by a row walk | `templates_page` materialises every row then slices (`work/selectors.py:684-695`) | TRUE |
| P3.14 | hold a help document | The only upload is `work-orders/{id}/attachments/upload-url` (`work/api.py:1733`) | TRUE |
| P3.20 / P3.21 | door tests; `supervisor-writes-a-rule.md` | — | STATED ×2 |
| P3.22 | assets — the page behind the asset's button | Unchanged (front end in `features/assets`; server is Work's) | TRUE |
| P3.23 | index for server paging | None added | TRUE |
| P3.24 | settings none | Accurate | STATED |
| P3.28 | a template's change history — no endpoint | No `work/templates/{id}/audit` route (`work/api.py:1779-1787`) | TRUE |
| P3.31 | rules stamp their MODULE as source — `DEF-WRK-4096` | `source = rule.source_module` (`work/rules.py:327`); `DEF-WRK-4096` OPEN; demo `work_order_rule_raises` = **0**. **Changed fact:** the order table's CHECK now holds **16** labels, not 13 (`metering/connections.py:601-618`) | CHANGED |
| P3.32 | two new overnight readers | Five readers (`work/rules.py:241-247`) | TRUE |
| P3.33 | continuous flow takes a service and a unit | `DEF-WRK-4097` OPEN | TRUE |
| P3.34 | six screen moments tick the rule's job | Not built (`work/from_flows.py` proposes; no rule pre-selection) | TRUE |
| P3.35 | a rule shapes the failed-job retry | Not built | TRUE |
| P3.36 | steps 2 and 4 are read by nothing | `assignment` / `escalation` stored as JSON (`work/rules.py:651`), never read by `_raise_one` (`:291-388`) | TRUE |
| P3.38 | one subject, one open job per template | `_already_raised` is per RULE (`work/rules.py:281`) | TRUE |
| P3.40 | each process raises on PG, red first | — | STATED |
| P3.41 | no migration for the rule set | **No longer true for the whole set:** P3.65 (several triggers) needs a child table — `trigger_kind` is one column (`work/rules_models.py:115-129`) | CHANGED |
| P3.42 | customers and metering read the pre-selection | Not built | TRUE |
| P3.44 | move a technician to another crew | `PATCH /work/technicians/{slug}` calls `set_unavailable` only (`work/api.py:882`) | TRUE |
| P3.46 | lift `UNSERVED_UNTIL_WAVE_G` | Still declared (`work/workforce.py:143`) though wave G landed 2026-09-05 — a stale hold (law 2's mirror) | TRUE |
| P3.47 | `est_duration` set on 0 of 43 | **0 of 40**; `_resolve_est_duration` reads the job TYPE, never the template's task minutes (`metering/connections.py:2586`) | TRUE |
| P3.51 | no library English reaches a clerk | Front-end kit | STATED |
| P3.52 | nothing writes `crew_skills` | Only `sample_workforce.py:367` writes it | TRUE |
| P3.53 | a contractor's phone and email | `crews` has no such columns (`work/models.py:1081-1087`) | TRUE |
| P3.55 | parts import drops the category | NOT re-run this round: `PARTS_COLUMNS` declares `category` as a lookup (`metering/import_runs.py:2244-2256`) and `test_cr077_parts_import.py` covers Validate only, never a file through Transform. Re-measured on a real file in round 2 before any fix | TRUE (unverified) |
| P3.57 | the seven escalations fire | Nothing reads `escalation` | TRUE |
| P3.58 | six escalation messages in Notifications | None of the six in `notifications/rule_catalog.py`. `sla_breach` exists and is still `trigger_blocked_by="OQ-249"` with the comment *"There is no SLA concept anywhere in this codebase"* (`rule_catalog.py:836-846`) — false since `BR-WRK-018` (`sla_hours`): a stale body | TRUE |
| P3.59 | reminders live in Notifications | Not built | TRUE |
| P3.61 | Last fired and Jobs raised | *This month* IS served (`work/rules.py:691`); last fired and all-time raised are not | CHANGED |
| P3.65 | several triggers on one rule | One `trigger_kind` per rule | TRUE |
| P4.4 | reassign = unassign + assign; the reason is lost | Two rows, no reason column (`work/edit.py:340-369`; append-only trigger `work/0009`) | TRUE |
| P4.5 | the match must advise, never block; `US-WRK-020` TC-4 goes red | Refusal at the write (`work/dispatch.py:748-770`). **Citation corrected:** the case asserting the old rule is `US-WRK-025` TC-3 (`tests/test_us_wrk_024_027_dispatch.py:293`); `US-WRK-020` TC-4 asserts the ADVICE list and stays. **`DEF-WRK-9533`** | TRUE |
| P4.6 | 🔒 the override is audited | Nothing to audit yet | TRUE |
| P4.7 / P4.9 | field-app acceptance; `technician-accepts.md` | Field-app document not in hand | STATED ×2 |
| P4.8 | acceptance columns exist before screens | Not yet (P0.2) | TRUE |
| P4.10 | settings none | Accurate | STATED |
| P4.11 | hold, cancel, completion, acceptance missing from the order's history | `order_audit` reads `work_order_assignments` only (`work/dispatch.py:614-658`). **`DEF-WRK-9532`** | TRUE |
| P4.14 | send a completed job back to the field | No door | TRUE |
| P5.2 / P5.8 | pause the SLA clock on hold; `held_at`, `held_seconds` | No columns, no pause | TRUE ×2 |
| P5.6 | performance paging | `by_job_type` is unpaged and the first-time-fix and per-type tallies loop over EVERY completed order in Python (`work/selectors.py:1355-1385`) | TRUE |
| P5.7 | `sla-breach.md` | — | STATED |
| P5.9 | the weighted SLA figure, red first | **Changed by PO answer (1):** today *SLA met* excludes undated jobs (`promised = orders.filter(due_at__isnull=False)`, `selectors.py:1336`) — 3 of 40 demo jobs carry a due date. The red case now asserts the DEFAULT target counts them | CHANGED |
| P5.10 | SLA per job type | SLA is per PRIORITY only (`work_priorities.sla_hours`) | TRUE |
| P5.11 | other module none | Accurate | STATED |
| P6.1 | tell the consumer: booked, moved, on the way, done | **Changed:** the catalogue already holds `appointment_window`, `technician_on_the_way`, `completion_receipt` (`notifications/rule_catalog.py:666-710`), but nothing sends three of them; *moved* is sent from the EDIT page only (`work/edit.py:544`), in-app only, never from a dispatcher's reschedule | CHANGED |
| P6.2 | tell the back office: at risk, declined, blocked | Not built | TRUE |
| P6.3 | print a work order | `work_documents.py` has no PDF path | TRUE |
| P6.4 | notification rules — a tenant chooses per event | **Changed:** the home already exists — Notification settings (`BR-NOT-017`, one home); Work adds catalogue rows, never its own rule table | CHANGED |
| P6.5 | four new consumer message kinds | **Changed:** three of the four already exist (above); one new kind (*visit moved*, today the `work_appointment_moved` category) | CHANGED |
| P6.6 | no message without a rule | — | STATED |
| P6.7 | notification rule rows (a new table) | **Changed:** a Work-owned rule table would be a second home against `BR-NOT-017`; the existing notification rule rows ARE the home (J6) | CHANGED |
| P6.8 | `customer-told-about-a-visit.md` | — | STATED |

**Count (89):** **TRUE 56** (one unverified, P3.55) · **CHANGED 10** · **DONE 0** · **STATED 23**.
Nothing the blueprint measured on `2.340.0` has been fixed since; 26 Work commits moved line
numbers, demo counts and three neighbouring facts (16 source labels, three catalogue kinds already
present, *This month* served).

## 7.2 · Defects filed this round (module WRK), each with a HELD case

`06-backend/tests/test_cr168_round1_held_defects.py` — ten cases, each `xfail(strict=True)`, each
run WITHOUT its marker first and failing for the stated reason (quoted in the docstring); `10
xfailed` with the markers. The day a fix lands, its case passes, strict turns that into a red that
names the defect, and the fixing lane removes the marker in the closing commit.

| Defect | Task | What a user meets | Failure on the tip |
|---|---|---|---|
| `DEF-WRK-9533` (high) | P4.5 | Cannot give a job to someone without the skill, though ruled *"a guideline, never a block"* | `ValidationError (work.dispatch.skill_mismatch)` |
| `DEF-WRK-9525` (high) | P1.34 | An office user completes a job, by field-result and by the edit page's *Complete* | `DID NOT RAISE` ×2 |
| `DEF-WRK-9526` | P1.31 | A finished job reads *Queued* / *Scheduled* | `'scheduled' == 'complete'` |
| `DEF-WRK-9527` | P2.13 | Unit 205 of 500 Main St accepted on a Kestrel Park job | `DID NOT RAISE` |
| `DEF-WRK-9528` | P2.14 | A per-unit water template raises a per-premises job with no service | `'per_premise' == 'per_unit'` |
| `DEF-WRK-9529` (high) | P1.15 | Tap-to-call empty on every job | `None == 'Sarah Miller'` |
| `DEF-WRK-9530` | P1.25 | The edit page opens on *Nobody yet* | `KeyError: 'id'` |
| `DEF-WRK-9531` | P3.4 / NFR-5 | The 201st crew or technician is never offered a no-skill job | `3 == 4` (cap lowered to 3 to run fast) |
| `DEF-WRK-9532` | P4.11 | A hold never appears on the order's Audit tab | `'hold' in []` |

**Already filed and still open, re-confirmed:** `DEF-WRK-4096` (four of five rule triggers raise
nothing — 0 raises on the demo), `DEF-WRK-4097` (leak rule catches every meter). **Stale bodies
noticed, not filed as defects** (law 1 — comments, no user-visible effect): `bulk_act`'s *"OQ-WRK-1497
… OPEN"*; `sla_breach`'s *"no SLA concept anywhere"*; `UNSERVED_UNTIL_WAVE_G`; and `DEF-WRK-3635`
still reads **open** in the register while `_refuse_if_cancelled` says it was fixed
(`metering/connections.py:8624-8640`) — each is corrected in the commit that builds its task.

## 7.3 · The proposed API contract (round 2 implements; names fixed once agreed)

**Fixtures come from the server, never hand-typed** *(added 2026-10-04 by lane SHAPE-SWEEP, `DEF-WRK-9606`)*.
This table names FIELDS; it does not fix their SHAPES, and on 2026-10-04 two lanes read the same row two
ways — `location.unit` as text and as `{id, label}` (`DEF-WRK-9600`, the order page crashed on every job
with a unit), `active` as sent and as absent (`DEF-WRK-9601`, *Put on hold* offered no reason) — with every
test green, because each side's fixture was typed by the side it tested. So **a Work screen's test serves
the server's RECORDED answer**: `10-scripts/cr168_capture_work_shapes.py` (over HTTP, `runserver` on
PostgreSQL) and `10-scripts/cr168_srv2_record_shapes.py` (through the views) write
`07-frontend/src/features/work/__fixtures__/`; `recordedServerShapes.typecheck.ts` makes `tsc` compare
every recording with the type the screen reads it through, and `recordedServerShapes.dom.test.tsx` mounts
the screens on them. **A lane that changes a read's shape re-runs the recorder in the same commit**, and
`tsc` names every screen type that disagrees; a lane adding a read adds it to the recorder. Never edit a
recording to make a check pass.

**Conventions.** Every list is paged in SQL (`page`, `per`, `clamp_page_size`; envelope `{results,
count, next, previous}` as `work_orders` uses today) — NFR-3. No list, picker or candidate set has a
maximum (NFR-5): a picker that needs "everybody" pages and searches like any other list. Every write
writes `audit_log` (hard rule 7). Cross-tenant ids read as absent (404), never 403 (hard rule 1).
Money stays 4 decimals stored, 2 shown; unit prices up to 4 (hard rule 2). A refusal carries a
`message_key` the screen translates; each sentence obeys B14 rule 33.

### Reads

| Endpoint | Returns (additions to today's shape) | Task · image |
|---|---|---|
| `GET /work-orders` | Six filters kept (`BR-WRK-026`); **`status=complete` reads completed jobs, accepted or not** (J3). Rows add `area` (walked from the premises, never `work_orders.area_id`), `technician_acceptance {state: pending\|accepted\|declined, at, reason}`, `hold {reason {code,name}, expected_return_on}\|null`, `accepted {by, at}\|null`, `sla {due_at, target: "priority"\|"default", at_risk: bool}`. Declared sorts: `priority`, `due_at`, `raised`, `order_no` | P1.6, P2.17, P4.1, P4.3 · 01 |
| `GET /work-orders/{id}` | adds `shape: open\|completed` (ruling 15/17), `customer {name, phone, account_no}\|null` (the job's account, else the current account on its unit — walked like the address), `location {premises, unit, asset {asset_no, serial}, address}`, `signature {printed_name, signed_at, refused, captured_by {name}, image_url (4-hour link)}\|null` — **only when `shape=completed`**, `timeline[] {kind, at, by {name}, detail}` | P1.2, P1.15, P1.21–24, P1.29, P4.2 · 03–06, 09 |
| `GET /work-orders/{id}/audit` | **paged**; the union of `work_order_assignments` and this order's `audit_log` rows: `{at, by {name}, act: assign\|unassign\|reassign\|schedule\|depart\|arrive\|hold\|resume\|cancel\|priority\|completed\|accepted\|sent_back\|accepted_by_technician\|declined_by_technician, reason, before_display, after_display, against_advice: bool}` — names and words, never ids | P4.11, P1.17 · 08 |
| `GET /work-orders/{id}/edit` | `technician {id, kind, name}`; `appointment {date, start, end}` in the UTILITY's time zone; `priorities[]` by rank | P1.25 · 12, 13 |
| `GET /work/candidates?template_id=&premises_id=&unit_ids=&on=&q=&page=&per=` and `GET /work-orders/{id}/candidates?q=&page=&per=` | **paged, uncapped**; every technician, crew and contractor, `Best fit` first: `{kind, id, name, advice {skill {name}\|null, has_skill: bool, area_match: bool, off_that_day: bool, jobs_that_day: int, certifications_lapsed[] {name, expired_on}}, best_fit: bool}`. Nothing is `eligible:false` any more (ruling 2; PO answer 2) | P2.5, P4.12, P4.13 · 12, 13, 16, 02 |
| `GET /work/raise/assets?unit_ids=&asset_type=&service=&q=&page=&per=` | paged assets on the ticked units: `{id, asset_no, serial, type {name}, service {code,name}, unit {label}, premises {address}}`; `q` matches asset no, serial and where (ruling 22) | P2.16 · 15 |
| `GET /work/templates?service=&asset_type=&scope=` | as today, plus the two filters the raise needs; footer `counts` from ONE SQL aggregate | P3.5, P2.11 · 43, 14 |
| `GET /assets/{id}/work-order-templates` | filtered by the asset's TYPE and its SERVICE (a template naming no service applies to every one); paged | P2.21 · 20 |
| `GET /work/crews?view=technicians\|crews\|contractors&q=&sort=&page=&per=` | one SQL query per view, `ORDER BY` + `LIMIT/OFFSET`; `counts {technicians, crews, contractors}` by aggregate; contractor rows add `phone`, `email`; crew rows `members` (counted, never typed) | P3.4, P3.49, P3.53 · 25, 27, 28 |
| `GET /work/technicians/{slug}` | adds `crew {id, name}`, `today {jobs}`, `this_month {closed, on_time, on_time_of, first_visit_pct, vs_estimate_pct}`; `UNSERVED_UNTIL_WAVE_G` retired | P3.46 · 31 |
| `GET /work/technicians/{slug}/jobs?f.period=&page=&per=` | paged jobs held by the person (current holder or any assignment row naming them) | P3.45 · 32 |
| `GET /work/technicians/{slug}/performance?period=` | the Performance arithmetic filtered to one person; `by_job_type` paged | P3.46 · 34 |
| `GET /work/templates/{id}` | each task row adds `instruction` (PO answer 3); help rows add `url` (document) or `link` (video/web) | P3.26, P3.25 · 44, 55 |
| `GET /work/templates/{id}/audit?page=&per=` | the `audit_log` trail of the template and its seven collections, in words | P3.28 · 47 |
| `GET /work/rules` / `GET /work/rules/{id}` | rows add `triggers[] {kind, params}`, `last_fired_at\|null`, `jobs_raised` (all time) beside `this_month`; `escalations[] {kind, after_hours, also_tell[] {kind: role\|user, id, name}}`; no `reminders` | P3.61, P3.65, P3.67 · 56, 62 |
| `GET /work/rules/{id}/jobs?page=&per=` · `GET /work/rules/{id}/audit?page=&per=` | paged | P3.62 · 63, 64 |
| `GET /work/rules/processes` | the thirteen processes ONCE: `{key, label, source_label, params[] {name, kind, unit?}, moment: overnight\|screen}` — the single list both the form and the server validate against | P3.30 · 57 |
| `GET /work/hold-reasons` | the tenant's lookup `{code, name, active, rank}` | P0.4 · 10 |
| `GET /work/performance?period=&page=&per=&sort=` | `by_job_type` paged; *SLA met* counts every completed job against `due_at`, else against the DEFAULT target from `created_at` (PO answer 1); held time excluded (P5.2); all tallies in SQL | P5.1, P5.6, P5.9 · 65 |
| `GET /work/at-risk?page=&per=` | open jobs whose target falls within the tenant's warning window, or already passed, held time excluded | P5.3 |
| `GET /work-orders/map` | **as today — NO `tiles` field (amended 2026-10-04, P3.3).** The PO chose Esri (`OQ-WRK-12787` CLOSED) and the map reads its ground from `GET /integrations/page-policy`'s `tile_host`, exactly as the Assets map does; a `tiles` answer here would be a second home for the tile host (`DEF-INT-4287`), so the stub proposed in §7.6 is not built | P3.3 · 24 |
| `GET /work-orders/{id}/print` · `GET /work/print/day-pack?date=&technician=` | `application/pdf`, rendered through the tenancy document store like every other printed document | P6.3 |
| `GET /work-orders/{id}/checklist` *(appended by lane ORDER-PAGE, round 2 — served)* | safety and task rows add `ticked_by_name` — who ticked the line on the phone, as words (`ticked_by` stays an id and is never drawn) | P1.29 · 06 |
| `GET /work-orders/{id}/attachments/{aid}/content` *(appended by lane ORDER-PAGE — served, `DEF-WRK-9594`)* | the photograph's bytes, same-origin, tenant-scoped, `private, no-store`; the viewer draws from it because the page policy refuses a storage host | P1.22 · 06, 09 |
| `GET /work-orders/{id}` *(appended by lane ORDER-PAGE — read, for SRV-1 to serve)* | `closed {by {name}, at}` (image 04's *Closed by*) and `accepted {by, at}` on the detail; **`signature.image_url` is a same-origin API path, never a storage link** (`DEF-WRK-9594`'s reason) | P1.24, P1.32 · 04 |

### Writes

| Endpoint | Body | What it does · refusals |
|---|---|---|
| `POST /work-orders` | as today plus optional `assignee {technician_id\|crew_id}` | The template's `scope` and `service` are COPIED when the payload omits them (`DEF-WRK-9528`); `est_duration` = the sum of the template's task minutes (P3.47); `area` is never asked (ruling 24); a premises-only raise names its unit, a unit-only or asset-only raise fills premises, unit, account and service by walking (P2.20). Refuses `work.order.unit_not_on_premises` (`DEF-WRK-9527`), `work.order.template_wrong_service` (P2.11), `work.order.asset_type_not_on_template` (P2.14), `work.order.asset_required` (ruling 20: an asset type chosen, no asset) |
| `POST /work-orders/bulk-raise` | `{template_id, premises_id, unit_ids[] \| asset_ids[], priority_id, due_on, window_start, window_end, technician_notes, assignee, idempotency_key}` | One job per unit (or per asset when an asset type is chosen); **one savepoint per job** (law 14), `{results[] {unit_id, asset_id, ok, id, order_no, reason}, done, failed}` (`BR-WRK-027`); a repeated `idempotency_key` returns the first answer; no batch number (`OQ-WRK-1497` closed). Refuses `work.raise.selection_empty`. **Proved on PostgreSQL** (P2.6) |
| `POST /work-orders/{id}/assignments` | as today, plus `act: "reassign"` with `{technician_id\|crew_id, reason}` (reason required on reassign) | **No skill or certification refusal** (ruling 2, PO answer 2): an assignment against advice succeeds, writes `audit_log` `work.order.assigned_against_advice {missing_skill, lapsed[]}` (P4.6 🔒). Reassign = ONE request, TWO rows (`unassign` + `assign`) carrying the same `reason` and `act_group` (J2), both technicians told (I5). Refuses `work.dispatch.reason_required` |
| `POST /work-orders/bulk` | as today; `assign` asks `{who, when}` | Per-order results unchanged; the per-order advice is in each result |
| `POST /work-orders/{id}/hold` | `{reason_code, expected_return_on?, note?}` | Writes `hold_reason_id`, `hold_expected_return_on`, `held_at`; audited. Refuses `work.hold.reason_required`, `work.hold.reason_unknown` |
| `POST /work-orders/{id}/resume` | `{}` | Back to the dispatch state before the hold; adds `now − held_at` to `held_seconds` (P5.2/P5.8) |
| `POST /work-orders/{id}/field-result` (metering's door) | as today | **Admits only the job's technician, or a member of its crew or contractor** (ruling 18, ruling 36); everyone else `work.order.closed_by_field_only` (`DEF-WRK-9525`). The close also moves `dispatch_state` to `complete` (`DEF-WRK-9526`) |
| `PATCH /work-orders/{id}/edit` | as today | `dispatch_state=complete` refused `work.order.closed_by_field_only`; `technician_id` round-trips |
| `POST /work-orders/{id}/accept` (exists) · `POST /work-orders/accept-bulk` `{ids[]}` | — | Bulk = a loop over the existing acceptance with a savepoint each and per-order results (P3.7, P1.36). **The acceptance is a money path** (cost lines, meter reads) and is proved on PostgreSQL (law 14) |
| `POST /work-orders/{id}/send-back` | `{reason}` | Only BEFORE acceptance: `state` back to `in_progress`, `dispatch_state` to `scheduled`, `field_data` kept, `accepted_by` stays NULL, the technician told. Refuses `work.order.already_accepted` (nothing accepted is ever re-opened — cost lines and meter reads are already written) (P4.14) |
| `POST /work/mobile/jobs/{id}/acceptance` | `{decision: accept\|decline, reason?}` | The technician's own acceptance (P4.7, shared with the field-app document); writes the acceptance columns; `decline` requires `reason`. Refuses `work.acceptance.not_yours` |
| `PUT /work-orders/{id}/readings/{rid}` | `{value, unit}` or, for a reading whose `kind` is `text`, `{value_text}` | A text reading is stored in `value_text` and **can never post as a meter read** (hard rule 3) — a template refuses `posts_as_meter_read` on a text reading (`work.template.text_reading_cannot_post`) (P1.33) |
| `PATCH /work/technicians/{slug}` | `{crew_id}` (plus today's availability fields) | Moves a technician; audited; the crew's member count is derived (P3.44) |
| `POST /work/crews` · `PATCH /work/crews/{id}` | `{kind, name, role_label, shift_start, shift_end, phone?, email?}` (phone/email for `contractor` only) | Three add forms (4·1d, 4·1e); refuses `work.crew.contact_contractor_only` |
| `PUT /work/crews/{id}/skills` | `{skills[] {skill_id, proficiency}}` | The technician's shape, audited (P3.52) |
| `POST /work/crews/{id}/members` | `{user_id}` or an invite | Add crew member (4·1a); a contractor's people get phone-only logins via identity — **field-app document, not round 2** (ruling 36) |
| `PUT /work/templates/{id}/tasks` (existing collection PUT) | rows add `instruction` (text, optional) | PO answer 3 |
| `POST /work/templates/{id}/help/upload-url` | `{filename, content_type}` | A template-scoped ticket, stored through the document store exactly as `evidence.py:399` does (P3.14). Help rows accept `kind: document\|link` with `link` an `https` URL (P3.25) |
| `POST /work/rules` · `PATCH /work/rules/{id}` | `{name, triggers[] {kind, params}, template_id, priority_id, assign_to {kind: area\|skill\|nobody\|technician\|crew, id?}, notifications[] {event_key}, escalations[] {kind, after_hours, also_tell[]}, enabled}` | `triggers[]` ≥ 1 (any of them raises; P3.65); `notifications[]` are catalogue keys, never text (`BR-NOT-017`); `escalations[].kind ∈` the seven (`unassigned, not_accepted, running_late, overdue, on_hold_too_long, failed, not_approved`); `also_tell` ADDS recipients, never removes the derived ones (`BR-NOT-021` narrowed for Work, PO 2026-10-04). Refuses `work.rules.trigger_required`, `work.rules.trigger_unknown`, `work.rules.escalation_unknown`, `work.rules.message_unknown`, `work.rules.reminders_live_in_notifications` (any `reminders` key) |
| `POST /work/settings/sla` | `{default_target_priority_id}` | PO answer 1: which priority's hours undated jobs are measured against; seeded `NORMAL` (72 h) |
| `PATCH /work/job-types/{id}` | `{sla_hours?}` | P5.10: a type's own target overrides its priority's; blank = the priority's |
| *(retired)* `POST /work/settings/lapse-policy` | — | **`BR-WRK-030` SUPERSEDED (PO answer 2):** the switch is retired; `block` refused `work.settings.lapse_policy_retired`; `work_settings.lapse_policy` stays as a lawful container read by nothing |

### Migrations (next free numbers at `9787009ee`; each has a down path; every one is 🔒 migration ordering → `HUMAN-REVIEW-PENDING` + a review-ledger row; RLS `FORCE` on every new tenant table in its own migration)

| # | What | Down |
|---|---|---|
| `work/0028` | `work_hold_reasons` (tenant lookup: code, name, rank, active; seeded *Weather · Waiting for a part · Customer not home · Access refused · Other*); `work_order_assignments` + `reason TEXT NULL`, `act_group UUID NULL` (the append-only trigger is untouched — adding a column is not an UPDATE of a row); `crews` + `phone`, `email`; `work_order_template_tasks` + `instruction TEXT NULL`; `work_order_template_readings` + `kind TEXT DEFAULT 'number'` (CHECK `number\|text`); `work_order_readings` + `value_text TEXT NULL`; `work_order_types` + `sla_hours INT NULL`; `work_settings` + `default_target_priority_id` FK | drop each |
| `work/0029` | `work_order_rule_triggers` (rule, kind, params JSON; existing `trigger_kind`/`params` copied in as row 1, the columns kept as lawful containers); `work_order_rule_escalation_fires` (work_order, kind, fired_at; UNIQUE `(tenant, work_order, kind)` — *once per job per kind*, P3.57) | drop tables (the copied trigger columns were never removed) |
| `work/0030` | RLS `ENABLE + FORCE` + tenant policy on `work_hold_reasons`, `work_order_rule_triggers`, `work_order_rule_escalation_fires` | drop policies |
| `metering/0071` | `work_orders` + `accepted_by_technician` (FK `technicians`, the reviewed cross-module FK set already holds `assignee_technician`), `accepted_at_technician`, `declined_at`, `declined_reason`, `hold_reason_id` (FK `work_hold_reasons` — **after `work/0028`**), `hold_expected_return_on DATE`, `held_at`, `held_seconds INT DEFAULT 0`; indexes `(tenant_id, state, completed_at)` for `status=complete` and `(tenant_id, premises_id)` for the area walk | drop columns, indexes |
| `metering/0072` (data) | P0.1: demo orders on `is_sample` rows take their type's default priority and its `due_at` from `created_at`; P1.31: `dispatch_state='complete'` where `state='completed'` — **only** where the row is not on hold or cancelled. Prints what it read and changed | the reverse is a no-op, stated (a corrected token is indistinguishable afterwards) |
| `work/0031` | P3.23: indexes for SQL paging — `technicians (tenant_id, crew_id)`, `crews (tenant_id, kind, name)`, `work_order_templates (tenant_id, active, name)` | drop indexes |

**`metering/0071` touches `work_orders`, the table the acceptance money path writes; no money
column moves.** No migration touches `notifications` (J6).

**Appended by lane SRV-1 (round 2), each with its reason — the contract's own rule for a field
added after agreement:**

| Added / moved | Where | Why |
|---|---|---|
| `work_order_readings.kind` | `work/0028` | the JOB's own copy must say a reading is text; re-reading the template would let a later template edit change what a job in the field accepts (`BR-WRK-008`, copy never link) |
| templates index `(tenant_id, active, name)` | `metering/0071`, not `work/0031` | `work_order_templates` is metering's model; a work migration cannot name it |
| `GET /work/hold-reasons` answers `{results: [...]}`, unpaged | `apps/work/api.py` | a tenant's own five-row reference list read whole into a dialog's select; its Settings home `/lookups/work_hold_reasons` pages |
| `GET /work-orders/{id}/audit` also carries `rows` (= `results`) | round 2 only | today's Audit tab reads `rows`; lane ORDER-PAGE moves it to `results` and the key goes in that commit |
| `GET /work-orders/{id}/edit` · `appointment.time_zone` | `apps/work/edit.py` | the zone the date and times are in, so the screen never guesses |
| `GET /work-orders/{id}/signature/image` | `apps/work/api.py` | the mark's bytes, same-origin, `private, no-store` — what `signature.image_url` points at |
| list rows · `sla.at_risk` = past its target | `apps/work/dispatch.py` | the tenant warning window is SRV-4's (P5.3); no window invented |
| `GET` beside `POST /work/settings/sla` | `apps/work/api.py` | the settings screen must read the current answer `{priority {id, code, name}, hours, chosen}` |
| `POST /work-orders/{id}/resume` answers `{order_no, dispatch_state, hold: null}`; hold answers `hold {reason {code,name}, expected_return_on, since}` | `apps/work/dispatch.py` | the dialog redraws from the answer without a second read |

### Seams crossing modules (all READ, except metering's own services called by name; `G78` stays green)

| Seam | New reader | For |
|---|---|---|
| `customers_seam.account()` | + `name`, `phone` (the current primary contact) | P1.15 |
| `customers_seam.current_account_for_unit(unit_id)` | the account in force on a unit | P1.15 (a job naming no account) |
| `metering_seam` | `premises_area(order)` walk; `asset_location(asset_id)` (asset → service point → unit → premises); `submit_field_result` / `accept_field_result` unchanged calls | P2.17, P2.20 |
| `assets_seam` | `asset_service_code(asset_id)`; `assets_for_units(unit_ids, asset_type, service, q)` returning a QUERYSET to page | P2.21, P2.16 |
| `notifications_seam` | `queue_document` for the consumer kinds; staff escalations through the notifications staff path with `also_tell` appended to the ruled recipients | P6.1, P3.57 |
| `tenancy_seam` | document store upload ticket and PDF render | P3.14, P6.3 |
| `identity_seam` | phone-only logins for a contractor's people | ruling 36 — **field-app document; not round 2** |

## 7.4 · Judgments that are ours (decision log row *"CR-168 ROUND 1 · THE WORK SERVER'S ANSWERS"*)

| # | Judgment | Why, with the figure |
|---|---|---|
| J1 | **A hold reason is a tenant lookup row (FK), never a CHECK list.** | The blueprint's own warning (P0.3): a CHECK makes *"Waiting for a permit"* a migration; a lookup makes it a Settings row, the shape every other Work list already has (`work_order_types`, `work_priorities`). |
| J2 | **Reassign is one request writing two rows (`unassign` + `assign`) that share a `reason` and an `act_group`; no sixth act token.** | Keeps `ck_work_order_assignments_act` and the append-only trigger (`work/0009`) exactly as signed (`BR-WRK-025`: *"five is the whole set"*) while the Audit reads it as ONE act with one reason (P4.4). |
| J3 | **Completed jobs are reached through the existing STATUS filter (`status=complete`), not a seventh filter.** | `BR-WRK-026` says six filters and a 400 on a seventh. 23 demo jobs are finished and unreachable from the list today; they become reachable with no new filter. |
| J4 | **The completion guard lives in metering's `submit_field_result`, so every door inherits it.** The job's technician, or a member of the crew or contractor it was given to, may close; nobody else. | Ruling 18 + `BR-MET-110`: *"A hidden button is not a rule"* (hard-won law 1). Two office doors close a job today (field-result, edit `complete`). |
| J5 | **Advice replaces the skill and certification refusals everywhere; an override writes `work.order.assigned_against_advice`.** | Ruling 2 + PO answer 2. `US-WRK-025` TC-3 is rewritten in the fixing commit; `US-WRK-020` TC-4 (the advice list) stays. |
| J6 | **No Work notification-rule table.** Work's events are catalogue rows in Notifications. | `BR-NOT-017`: one home. P6.7's *"a rule table exists"* is already true there. |
| J7 | **The default SLA target is a setting naming a priority, seeded NORMAL (72 h).** | PO answer 1 says *"the Normal priority's hours … a tenant setting"*; naming the priority means a tenant who changes Normal to 48 h moves undated jobs with it. Worked: a job raised 10/01 09:00 with no date is due 10/04 09:00. |
| J8 | **A text reading never posts as a meter read.** | Hard rule 3: a meter read needs a number and a unit; `W-5000-N` is neither. |
| J9 | **Send back is refused once accepted.** | Acceptance writes cost lines and meter reads; un-accepting would leave them standing behind a job the field is still working (hard rule 4's shape). |

## 7.5 · For the PO — nothing collides with a signed money rule

No ❄️ B4/B5 figure, no CONFIRMED `BR-RAT` rule and no RLS policy moves. The two money-adjacent
points are handled inside signed rules: the acceptance path (cost lines, meter reads) is unchanged
and proved on PostgreSQL, and *send back* is refused after acceptance (J9). The cost-per-job figure
on Performance sums ROUNDED lines (`selectors.py:1365`) — that is signed `BR-WRK-051` (*"the sum of
the rounded displayed lines"*, `costing.py:40-45`), not a breach of hard rule 2's *round at display*.

## 7.6 · The one open question, and where its stub raises

| Id | Question | Stub |
|---|---|---|
| **`OQ-WRK-12787`** — ⚖️ **CLOSED 2026-10-04** | Which map tile provider draws the dispatcher's map? PO 2026-10-04: *"for Map i will provide details"*, then the same day: *"DECIDED: yes, use Esri. Our Assets map already uses Esri's public street tiles with no key … Do not ask about this again."* | **No stub was ever built and none is now:** `apps/work/map_tiles.py` and the `tiles` field never existed. The map reads `tile_host` from `GET /integrations/page-policy` through `07-frontend/src/features/integrations/basemap.ts`, the module the Assets map also imports (lane W-MAP, P3.3). |

The other three items the brief named are ANSWERED (decision log, *"THREE WORK ANSWERS"*) and are
built into §7.3, not minted.

## 8 · Rounds, lanes, versions and rollback (P0 → P6, at most five lanes at once)

The order is the blueprint's — **P1 first, because it carries the money path and loses work today** — adjusted by
what round 1 measured: `DEF-WRK-9583` (no field technician can sign in) blocks the whole phone and ships first, alone;
every server task lands before or with the screen that reads it, against §7.3's contract (the CR-165/166/167 pattern:
field names fixed; a field added by any lane is appended to §7.3 with the lane and the reason, in the commit that serves
it). Each lane owns its files; two lanes never edit the same screen file in one round.

| Round | Lane | Builds (tasks) | From images | Fixes | Depends on |
|---|---|---|---|---|---|
| **R1** | WORK-CR · WORK-SRV | This CR: §4 re-measure, §5 field map and task re-validation, §6 the 34 observations, §7 server answers and contract, §8 | all 65 | — (28 + 9 defects filed, 10 held tests) | — |
| **R2** | **IDN-FIX** | The field technician's sign-in: `POST /auth/session` carries the surface the field app declares, server-checked; the web form names the refusal | — | `DEF-WRK-9583` | — |
| R2 | **SRV-1** | P0.1–P0.5 migrations (`work/0028`–`0031`, `metering/0071`, `0072`); P1.6, P1.15, P1.23, P1.25, P1.31, P1.33, P1.34; P4.11 (audit union); the default SLA target setting (PO answer 1) | — | `9525`, `9526`, `9529`, `9530`, `9532`, `9571` | §7.3 agreed |
| R2 | **ORDER-PAGE** | One order, both shapes: P1.2, P1.16–P1.24, P1.28–P1.30 (order page), P1.32, P1.35, P4.2, P4.3 (hold dialog); *Mark complete* and the office's ticks removed (ruling 18) | 03–11 | `9581`, `9584`, (screen half of `9525`) | SRV-1's reads |
| R2 | **ORDERS-LIST** | Orders and the edit page: P1.1, P1.3, P1.4, P1.13, P1.26, P1.27, P1.30 (edit page, list), P2.1; Approvals: P1.5, P1.7, P1.36, P3.7 | 01, 02, 12, 13, 21–23 | `9562`, `9563`, `9569`, `9570`, `9575` | SRV-1 |
| **R3** | **SRV-2** | Raise and assign: P2.5, P2.9–P2.14, P2.17, P2.20, P2.21, bulk raise (savepoint per job, idempotent), candidates paged and uncapped; P4.4–P4.6 (advice, never a block; override audited 🔒), P4.8, P4.14 (send back) | — | `9527`, `9528`, `9531`, `9533` | R2 |
| R3 | **RAISE** | The raise and its two doors: P2.2–P2.4, P2.15, P2.16, P2.18, P2.19 (account and asset arrive filled; the asset door's one-page form retired, ruling 35) | 14–20 | `9572`, `9582`, `4752` | SRV-2 |
| R3 | **ASSIGN** | Advice beside every name and bulk assign: P4.1, P4.12, P4.13 (on 01, 02, 12, 13) | 01, 02, 12, 13 | — | SRV-2; ORDERS-LIST landed |
| R3 | **MAP** | P3.1 cluster, P3.2 a pin opens the order; **tiles BUILT 2026-10-04** (P3.3, Esri via the shared basemap module — `OQ-WRK-12787` CLOSED; pins still load if tiles fail) | 24 | `9561` (pins half), `9576` | — |
| **R4** | **SRV-3** | Crews and templates: P3.4, P3.5, P3.14, P3.22, P3.23, P3.28, P3.44, P3.46, P3.47, P3.52, P3.53, P3.55; task instruction text (PO answer 3) | — | `9587` | R3 |
| R4 | **CREWS** | Three lists, the add forms, one technician's four tabs: P3.27, P3.43, P3.45, P3.48, P3.49 | 25–34 | — | SRV-3 |
| R4 | **PARTS** | P3.8–P3.11, P3.50, P3.54, P3.56 and the import's words | 35–42 | `9574`, `9578`–`9580`, `9585`, `9588` | SRV-3 (category) |
| R4 | **TEMPLATES** | P3.12, P3.13 (+ instruction text), P3.15, P3.25, P3.26, P3.29 — one summary component for Review and Overview (B14 rule 43) | 43–55 | `9565`–`9568`, `9577` | SRV-3 |
| **R5** | **SRV-4** | Rules and the promise: P3.30–P3.38, P3.57–P3.59 (Notifications catalogue rows, other module), P3.61, P3.65; P5.2, P5.6, P5.8–P5.10, the at-risk read | — | `4096`, `4097` | R4 |
| R5 | **RULES** | Three-step builder on `WizardFrame`, triggers and escalations as rows, *Also tell*, a rule's own page: P3.16–P3.19, P3.37, P3.39, P3.60, P3.62–P3.64, P3.66, P3.67 | 56–64 | `9564`, `9573`, `5066` | SRV-4 |
| R5 | **PERFORMANCE** | P5.1 (headline agrees with rows; 72 h default), P5.3 at-risk board, P5.4 schedule board, P5.5 bulk raise across buildings — the three boards are named, not drawn: built from the kit under B14 rule 44, each put to the PO as a photograph before it ships | 65 | `9586` | SRV-4 |
| **R6** | **SRV-5** | P6.1–P6.8: the consumer and back-office messages through Notifications (one home, `BR-NOT-017`), a work order and a day's pack printed | — | — | R5 |
| R6 | **I18N** | Every new and changed string in all eleven catalogues, each in its own language (rule 35) — ruling 1's eleven values for *Approvals* first; retired keys through `10-scripts/i18n_fanin.py` | all | — | R2–R5 English settled |
| **R7** | **WALK** | The web walk: photograph the built screens in the **same 65 states**, side by side with `05-prototype/work-backoffice-2026-10-04/images/` into `08-qa/work-2026-10-04/after/`; re-run the 34 observations; file what it finds first, fix, close; (`OQ-WRK-12787`'s stub is gone — the PO named Esri on 2026-10-04 and P3.3 built it) | all 65 | whatever the walk finds | R2–R6 |

**Not scheduled, and why:** rulings 4 and 36 and P4.7 / P4.9 live in the technician field-app document, which is
not in hand; the contractor's phone-only logins (ruling 36) wait with it. The map's tile layer waited on the PO
(`OQ-WRK-12787`) until 2026-10-04, when they chose Esri; it is built (P3.3).

**Rules every lane follows here:** build from the images (rule 42) with our UI standard for spacing, type and
components (rule 44), every selection table the kit `TableArray`; action buttons top right (ruling 16, B14 rule 2);
a defect is filed before it is fixed and its test shown RED first — WORK-SRV's ten held cases
(`06-backend/tests/test_cr168_round1_held_defects.py`, strict xfail) turn red on the day their fix lands and the fixing
lane removes the marker in the closing commit; the acceptance path (cost lines, meter reads) and the bulk raise are
proved on PostgreSQL (law 14); every new tenant table gets RLS `FORCE` in its own migration; 🔒 migration-ordering
files ship `HUMAN-REVIEW-PENDING` with a review-ledger row.

**Versions.** Round 1 ships no product code — this file, the decision-log row, five walk scripts, 59 photographs and
37 defect rows across both lanes — so it carries **no version**. Each later push takes its own number at push time
with `10-scripts/allocate.py version --bump change` (a fix-only push `--bump fix`, e.g. IDN-FIX) and `--verify`,
records it in `CHANGELOG.md` and the version source of truth as the `CR-165`/`CR-166`/`CR-167` commits did, and
appends its record to this file as a new section (§9 onward) with the version, the images it was built from, and
the defects it closes.

**Rollback.** R1: none needed (records only). Screens (every front-end lane): redeploy the previous build; no stored
fact changes from a screen alone. Server: each migration's down path is in §7.3's table — `metering/0072` (the data
task) is one-way and says so, because a corrected dispatch status is indistinguishable afterwards; the rule-trigger
copy in `work/0029` keeps the old columns, so a rollback loses no rule. **The acceptance path writes cost lines and
meter reads**: a rollback after acceptances under the new code leaves those rows standing — they are correct under
both versions, which is why the guard (J4) changes WHO may close, never what a close writes. IDN-FIX rolls back by
redeploy; a field technician then cannot sign in again (today's state).

## 9 · Round 2 — lane IDN-FIX: the field technician's sign-in (`2.493.2`)

**Built from:** no image (§8 row R2 IDN-FIX) — `BR-WRK-043` and `OQ-WRK-1494` as ruled; the phone's routes as they stand.
**Closes:** `DEF-WRK-9583` (critical) and `DEF-WRK-9593` (critical, filed by this lane: found by its own walk the
moment sign-in worked). Judgments: decision log *"CR-168 ROUND 2 · IDN-FIX"* (J1–J6).

| What | Before (`2.490.6`) | After (`2.493.2`) |
|---|---|---|
| `POST /auth/session` | no `surface`; every attempt read as the web | `surface` = `web` · `mobile` (absent = `web`); unknown or `both` → 422; the login's `surface_scope` decides |
| Technician on the field app | 403 `identity.signIn.fieldAppOnly` | 201, lands on *Today* (after the forced change, `?next=/work/mobile`) |
| Technician on the office sign-in | *That email or password is incorrect.* | *Sign in on the field app.* + a *Field app* link to `/{tenant}/work/mobile/signin` |
| Office-only login on the field app | (scope never reached) | 403 *Sign in on the web app.* (`identity.signIn.webAppOnly`, 11 catalogues) |
| Clerk on the default scope `both` | — | signs in on either door |
| Wrong password, either door | generic | generic, unchanged (`BR-IDN-002`) |
| Signed-in technician: `/me`, `/me/password`, `/work/mobile/*`, a job's evidence routes | 403 on every one (`AnyTenantRole` never admitted the role) | `FieldAppRole`; evidence routes and sync reach the technician's OWN job only (404 otherwise); office routes stay 403 |
| Phone with no session | an empty day | sent to its own sign-in (only on a 401; offline keeps the stored day) |

**Tests, red first.** Server on PostgreSQL 16: `06-backend/tests/test_def_wrk_9583_field_sign_in.py` — 7 red → 14 green
for `9583`, then `9593`'s cases (an invited technician sets a password and reads Today — red 403 before; four office routes
stay 403; own-job scoping — red `DID NOT RAISE` with the check sabotaged), 20 green; 168 passed across identity sign-in/profile, workforce, sync, evidence and session
binding. Screen: `07-frontend/src/features/identity/fieldSignIn.dom.test.tsx` — 5 red on the old page → 7 green; identity,
the phone and routing 291 passed.
**Proof.** API: `08-qa/work-2026-10-04/idn-fix/api-proof.txt`. Browser at 1440 (`10-scripts/def_wrk_9583_field_signin_walk.mjs`):
`idn1-technician-on-office-signin` · `idn2-wrong-password-generic` · `idn3-field-app-signin` ·
`idn4-technician-forced-change` · `idn5-technician-on-today`.
**Rollback.** Redeploy `2.493.1`; no migration and no stored fact changes. A field technician then cannot sign in again (the
state before this round), as §8 says.
**Left.** The field app's sign-in reuses the office lede (*"…jump straight to your dashboard."*); the phone's own words for
it are the technician field-app document's, not in hand (§8 *Not scheduled*). The declared surface is not bound to the
session (decision log J6's last sentence).

## 10 · Round 2 — lane ORDER-PAGE: one order, both shapes (`2.495.0`)

**Built from images 03–11** (B14 rules 42, 44, 37; ruling 16 — actions top right). Tasks **P1.2, P1.16–P1.24,
P1.28–P1.30 (order page), P1.32, P4.2, P4.3** — and **P1.35 found already done** (`DEF-SHL-6756`, 2026-09-25: the
wizard's current step is readable; nothing to build). Files: `07-frontend/src/features/work/OrderDetailPage.tsx`
(rewritten, 1,139 → 560 lines) and five components under `features/work/orderPage/` (B14 rule 43) —
`OrderOverview`, `OrderChecklist` (plan / record / parts), `OrderHistory`, `PhotoViewer`, `HoldDialog` — plus
`orderPageEndpoints.ts` (§7.3's shapes, every new field optional so the page draws what SRV-1 serves as it lands),
`orderShape.ts`, `orderFormat.ts`. All five component files are on `route-b-migrated.txt`.

**What changed on the page.**

| Image | Today (`2.490.6`) | Now |
|---|---|---|
| 03 Overview, not completed | six tabs; *Mark complete* leads the head; Overview = Type · Service (`water`) · Raised by · Template version | **four tabs** (ruling 12); head **Reassign… · Put on hold… · Cancel order** (*Resume* once held); *The job* adds Meter (only where the job has an asset) and Due; **Location** (Address · Unit · Area · Gate code · Access notes) and **Customer** (Account · Holder · Phone) are panels; the line under the title reads address · unit · account · holder · meter · priority · technician · window; the service by its name (P1.19) |
| 04 Overview, completed | the open job's head, pills *Scheduled · Completed* | head **Accept ✓** alone (P1.32, confirmed first, `POST …/accept`); pills dispatch · state · outcome · *Awaiting approval* / *Accepted*; *The job* shows Outcome and Closed by; **Signature** panel (mark, Signed by, When, Taken by, *View* opens the viewer) — on a completed job only (ruling 15) |
| 05 Checklist, the plan | office tick boxes on every safety line and task; tasks a list; ranges `18.0000–96.0000`; *EFFECT · Marking complete* box | **no tick box anywhere** (ruling 18); safety as a list; **tasks a table** `# · Task · Minutes · Photo` (ruling 14); readings `Reading · Unit · Range · Photo required`, ranges `0–99,999,999` (P1.18); no values, no photographs; the effect box is gone with *Mark complete* |
| 06 Checklist, the record | the same as 05 | `✓ … · D. Ortiz · <when>` on every safety line; *6 of 6 done*; tasks gain **Done** (who · when) and the photograph in **Photo**; readings gain **Value** and **Photograph**; the footer counts and the one-sentence consequence |
| 07 Parts | `1.0000 roll` | `2 each` (P1.18) |
| 08 Audit | Act · Who · When, When raw ISO, Who = the holder | **Act · To · By · When · Window** — To the holder, **By the person who acted**, When in the utility's zone and format, the window (P1.16, P1.17; `DEF-WRK-9584`); every §7.3 act has a word in all eleven catalogues, an unknown one reads *Changed* (P4.2) |
| 09 Photo viewer | none | the picture, Taken by · When · For (*Task 1 of 6* or the reading), *1 of 3*, *‹ Previous · Next ›* (P1.22) |
| 10 Put on hold | posted `{}` at once | the dialog: **Reason\*** (the tenant's lookup, `GET /work/hold-reasons`), **Back on**, **Note**, *The due time pauses while held.*, *Back · Put on hold* (P4.3); a held job shows *Held for* and *Back on* on the Overview and **Resume** in the head |
| 11 Cancel | *Cancel · Cancel this order* | ***Keep the order*** *· Cancel this order* (P1.20) |

**Defects.** `DEF-WRK-9584` **fixed and closed** (the server had served `by` and the window since wave G; the tab
dropped them). `DEF-WRK-9581` — the **screen half is built**: Meter, Unit, Holder and Phone draw from §7.3's
`location` and `customer` the moment SRV-1 serves them; the row stays open until a walk shows them filled.
`DEF-WRK-9525` — the **screen half is built** (no *Mark complete*, no office tick, the page never posts
`field-result` — asserted); the server half and the held case are SRV-1's. **`DEF-WRK-9594` filed and fixed (new,
high):** a job's photographs could never be shown on a staff screen — `GET …/attachments/{aid}` answers a presigned
link on the storage host and the page policy draws images only from itself (`img-src 'self' data: blob:`); on the
local store the link is `file://`. Now `GET /work-orders/{id}/attachments/{aid}/content` serves the bytes through the
session (tenant-scoped, the same 404 across utilities, `private, no-store`) and the viewer draws from it.

**Red first (quoted).** `orderPage/orderPage.dom.test.tsx` run against the page at `5be42bfb3` in a scratch worktree:
**16 failed / 1 passed of 17** — e.g. *expected [ 'Overview', 'Checklist', …(4) ] to deeply equal [ …(2) ]*, *the
line lacks Unit 1*, *expected [ 'Act', 'Who', 'When' ] to deeply equal [ 'Act', 'work.order.audit.to', …(3) ]*,
*expected [ 'Mark complete', 'Reassign…', …(2) ] to deeply equal [ 'Reassign…', 'Put on hold…', …(1) ]*, *expected 4 to
be +0* (four tick boxes), *Unable to find role="dialog"* (hold). ⚠ The first run reported 17 of 17 failed with
*document is not defined* — the file lacked its `// @vitest-environment jsdom` line; that red proved nothing and was
re-run (law 7). Server: `tests/test_cr168_order_page_ticked_by_name.py` on the old code — *KeyError: 'ticked_by_name'*,
*module 'apps.work.evidence' has no attribute 'attachment_bytes'*, *Resolver404*. **Green:** 17/17 and 4/4; the
order page's two older suites rewritten case by case (six-tab, *Mark complete* and lock cases replaced with their
ruling-18 opposites, never deleted silently) — 50/50 across the three files; work + styles + i18n suites 503 passed;
`tsc` clean (proved able to fail first).

**Added to §7.3 by this lane** (served by this lane, or read when SRV-1 serves it):
`GET /work-orders/{id}/checklist` — safety and task rows add **`ticked_by_name`** (served here); `GET
/work-orders/{id}/attachments/{aid}/content` (served here, `DEF-WRK-9594`); `GET /work-orders/{id}` — the page also reads
**`closed {by {name}, at}`** (who closed it in the field, image 04's *Closed by*) and **`accepted {by, at}`** on the
detail, falling back to the holder and `completed_at` until served; **`signature.image_url` must be a same-origin
API path, not a storage link**, for the reason `DEF-WRK-9594` records (SRV-1, P1.23).

**Photographs** — `08-qa/work-2026-10-04/after/03…11-*.png`, Chromium 1440 on PostgreSQL `sbh_worder`, every one
opened; jobs raised by `10-scripts/cr168_order_page_seed.py` (WO-0041 open, WO-0042 completed by D. Ortiz's own user —
ruling 18), walk `10-scripts/cr168_order_page_walk.mjs`. **Side by side, what still differs and why:** Unit, Meter,
Holder and Phone read *—* until SRV-1 serves `location` and `customer` (P1.2/P1.15); the signature panel shows no mark
until P1.23; the hold dialog offers no reason until `GET /work/hold-reasons` lands (P0.4) — all three are SRV-1's
reads, already coded against; *Send back…* (image 04) is **not drawn** — its endpoint is P4.14 (round 3, SRV-2), and a
button over nothing would claim a capability (law 1); Service and Due read *—* on the demo job (no service copied from
the template, `DEF-WRK-9528`; no priority, P0.1). Dates read in the tenant's own format (`10/04/2026 02:05`) where the
drawing illustrates *25 Sep, 9:41 AM* — rule 37/44, the standard wins.

**Rollback.** Redeploy `2.494.1`. No migration; the two server additions are reads (a field and a route) and are
safe to leave behind.

## 11 · Round 2 — lane ORDERS-LIST: Orders, the edit page and Approvals (`2.493.0`)

**Built from the images** (B14 rules 42, 44, 37): 01 (Orders), 02 (Assign in bulk), 12 (Assign a job), 13 (Reassign a job), 21 (Approvals), 22 (Approvals · Accept), 23 (Approvals · Accepted). Judgments in the decision log row *"CR-168 ROUND 2 · ORDERS, THE EDIT PAGE AND APPROVALS"*.

| Task | What landed | Image |
|---|---|---|
| P2.1 · P1.30 (list) | *+ New work order* in the page header, accent tier, on every state of the list; the row under the pager is gone (`DEF-WRK-9562`, `DEF-WRK-4105`) | 01 |
| P1.4 | *Reschedule selected…* and *Assign selected…* take the kit's date picker and a window list (*Any time · 08:00–12:00 · 12:00–17:00*); one `visitWindow.ts` writes the moments for the bulk dialogs and the edit page (`DEF-WRK-9570`). *Assign N orders* also asks the date and window and says *Each person is told on their phone.* | 02 |
| P1.1 | A refused bulk act answers in its dialog; the edit page's save and cancel show the server's sentence in a `role="alert"` line and stay on the page | 02, 12 |
| P1.3 | *Assigned to* names each holder with its kind (*Field crew B · Crew*); the kind decides `technician_id` or `crew_id` (`DEF-WRK-9563`) | 12, 13 |
| P1.26 | Change effects lists what THIS save does: the new holder told, the old holder told, the technician's phone when anything else moves, the customer only when the day or window moves, the audit | 12, 13 |
| P1.27 (edit page) | The commit reads *Assign ✓* on a job nobody holds, *Reassign ✓* on one somebody does; the page opens on the holder (resolved by kind and name until SRV-1's P1.25 serves the id) | 12, 13 |
| P1.30 (edit page) | *Cancel · Cancel work order · Assign ✓* top right; the effects box under the title; *Complete* no longer offered as a status (ruling 18); Date has *Today*; help lines under Window and Area | 12, 13 |
| P1.13 | *Approvals* in all eleven catalogues, each in its own words (ruling 1, B14 rule 35): Freigaben · Aprobaciones · Validations · मंज़ूरियाँ · Persetujuan · Approvazioni · 承認 · 승인 · Aprovações | 01, 21 |
| P1.5 · P1.7 | The eye opens `/work/orders/{id}` on every row (`DEF-WRK-9575`); the empty queue's *Open work orders* opens Orders | 21 |
| P1.36 · P3.7 | Select column, ✓ per row, *Accept selected… (N)* top right; the confirm *Accept WO-0043?* · *The service goes live. The customer is told.* · *Keep waiting* / *Accept ✓*; one request per order with a per-order answer; toast *WO-0043 accepted · service live* | 21, 22, 23 |

**Not built here, and whose it is:** the advice beside each name and *Best fit* (image 12; lane ASSIGN, P4.12, round 3) · image 13's *Why it moves* (needs the reassign act with a reason, lane SRV-2, round 3) · the order PAGE's *Assign…* word on an unassigned job (P1.27's order-page half — `OrderDetailPage.tsx` is lane ORDER-PAGE's file this round) · `POST /work-orders/accept-bulk` (contract §7.3; no R2 lane builds it — the screen loops the single accept meanwhile).

**`DEF-WRK-9569` stays OPEN:** the list's server read is open-only, so an accepted order still cannot be found. The screen's *Status: Complete* filter is ready; the server half is lane SRV-1's (P1.6, P1.31). `06-backend/tests/test_def_wrk_9569_accepted_order_findable.py` holds it with a strict xfail that goes red the day the fix lands.

**Tests:** `07-frontend/src/features/work/cr168OrdersList.dom.test.tsx` — 20 cases, all 20 red on the tip before the fix (failures quoted in the lane report), green after. **Version** `2.493.0`. **Rollback:** redeploy `2.492.1`; no migration and no stored data change.

**After-walk (`2.493.1`, PostgreSQL 16 `sbh_wlist`, 1440):** `08-qa/work-2026-10-04/after/` — `01`, `02`, `02b`, `12`, `12b`, `13`, `21`, `22`, `23` (each opened, none blank) with `ORDERS-LIST-side-by-side.md`; scripts `10-scripts/cr168_orders_list_walk_prep.py` (closes three demo jobs as their technician so the queue has rows) and `10-scripts/cr168_orders_list_after_walk.mjs`. The walk found one fault of this round's own and it is fixed in `2.493.1`: a crew-held job opened on *Nobody yet* because the crew's list name carries its head-count. Defects closed with `b9a0bf28a`: `DEF-WRK-9562`, `9563`, `9570`, `9575`, `4105` (stale since `DEF-WRK-4121` put the button under the table; now asserted in the page header on a populated list and photographed in `01`), `DEF-BIL-9591`.
## 12 · Round 2 — lane SRV-1: the Work server, first round (`2.496.0` schema · `2.497.0` behaviour)

**Built** (server only; screens are ORDER-PAGE's and ORDERS-LIST's): P0.1–P0.5 (`work/0028`–`0031`,
`metering/0071`, `0072`), P1.6, P1.15, P1.23, P1.25, P1.31, P1.33, P1.34, P4.11, the hold-reason lookup
and `POST …/hold` with a reason + `POST …/resume` (P0.3/P0.4 — the hold dialog reads them), and the
default SLA target (PO answer 1). Judgments: decision log *"CR-168 ROUND 2 · SRV-1"*; additions to the
contract: §7.3 appendix.

| Task | What a user gets | Where |
|---|---|---|
| P0.1 · `DEF-WRK-9571` | demo jobs carry a priority (40 of 40); new demo builds raise at Normal | `metering/0072`, `metering/sample_data.py`, `work/sample_field_work.py` |
| P0.2 · P0.3 · P0.4 | technician acceptance, hold reason, return date and held time columns; five seeded hold reasons, a Settings list | `metering/0071`, `work/0028`, `work/lookups.py`, `tenancy/services.py` |
| P1.6 · `DEF-WRK-9569` | `GET /work-orders?status=complete` lists finished jobs, accepted or not (an accepted order is findable again — ORDERS-LIST's held case released); rows add `area` (walked), `technician_acceptance`, `hold`, `accepted`, `sla`; sorts `priority`, `due_at`, `raised`, `order_no` | `work/dispatch.py` |
| P1.15 · `DEF-WRK-9529` | the job names its customer and phone — its own account, else the account in force on its unit | `work/seams/customers_seam.py`, `work/mobile.py` |
| P1.23 | the signature serves `captured_by` and `image_url` — a SAME-ORIGIN path, `GET /work-orders/{id}/signature/image` (the bytes under the session; ORDER-PAGE's `DEF-WRK-9594` reason); on the order only once completed, beside `closed {by {name}, at}` (image 04's *Closed by*, read from the close's own audit row) | `work/evidence.py`, `work/dispatch.py`, `work/api.py` |
| P1.25 · `DEF-WRK-9530` | the edit form opens on the holder (with its id), the appointment in the utility's zone, priorities by rank | `work/edit.py` |
| P1.31 · `DEF-WRK-9526` | a closed job reads Complete (a held or cancelled one keeps its state) | `metering/connections.py`, `metering/0072` |
| P1.33 | a reading that is words is stored and never posts as a meter read | `work/0028`, `work/evidence.py`, `work/templates_svc.py`, `work/order_copies.py` |
| P1.34 · `DEF-WRK-9525` | only the technician (or crew/contractor) given the job may close it; the edit page cannot set Complete | `metering/connections.py`, `work/edit.py` |
| P4.11 · `DEF-WRK-9532` | the order's history pages hold, resume, cancel, priority, completed and accepted beside the assignment acts; a reassign is one line with its reason | `work/dispatch.py`, `work/seams/audit_seam.py` |
| PO answer (1) | `GET`/`POST /work/settings/sla` — the default target names a priority, Normal (72 h) until changed | `work/workforce.py` |

**Migrations, up → down → up on PostgreSQL 16** (`sbh_wsrv1`, the seeded brazosbend demo): up printed
*5 reason row(s) seeded · 40 sample order(s) given a priority (37 dated from it), 23 finished order(s)
moved to Complete · 7 rule(s) read — 7 trigger row(s) copied*; down unapplied all six (table gone, 0 of
the new columns left); up again re-seeded 5 reasons and changed 0 orders (idempotent); `pg_class` reads
ENABLE + FORCE on all three new tables. Demo before → after: 40 jobs, priority 0 → 40, Complete 0 → 23.

**Defects closed:** `DEF-WRK-9525`, `9526`, `9529`, `9530`, `9532`, `9569`, `9571` — each held case released
in the closing commit (`tests/test_cr168_round1_held_defects.py`, four still held for SRV-2: `9527`,
`9528`, `9531`, `9533`).

**Rollback:** redeploy 2.496.0 to take the behaviour back (the schema is inert without it); to take the schema back too, redeploy 2.495.2 and `migrate work 0027` (six migrations reverse cleanly; `metering/0072`'s
reverse is a stated no-op). Under the old build an office user can close a job again.

## 13 · Round 3 — lane MAP2: the map a dispatcher can use (`2.498.0`) and the order page re-shot

**Built** (front end only; the map read is unchanged): P3.1, P3.2 and the key the blueprint's convention R10
asks for. Judgments: decision log *"CR-168 ROUND 3 · MAP2"*.

| Task | What a user gets | Where |
|---|---|---|
| P3.1 · `DEF-WRK-9598` | jobs at one place are ONE mark carrying the count; pressing it lists *N jobs at this place* beside the map, each a door to its order; a cluster is hollow when any job in it is unassigned. Tab · Enter · Enter reaches an order without a mouse | `features/work/MapView.tsx` (`groupByPlace`) |
| P3.2 · `DEF-WRK-9576` | a pin opens the order's own page (`WRK-02`), through the same `workOrderDetailPath` the Orders list's 👁 uses | `features/work/WorkMapPage.tsx` |
| key · `DEF-WRK-9599` | *Key* · hollow *Unassigned* · solid *Assigned*, bottom-left of the map | `features/work/MapView.tsx` |

**Red first** (`MapView.test.tsx`, 8 new cases, all failing before the change: no `[data-cluster]`, no panel,
17 marks for 17 orders where 5 places were expected, no key, and the pin landing on the `edit` route), then
18 of 18 green; `tsc` clean (proved able to fail); the Work folder, the i18n suites and
`routeBUtilities.test.ts` 43 files green. Walk: `10-scripts/cr168_work_map_clusters_walk.mjs`.


## 14 · Round 3 — lane ASSIGN: advice beside every name, bulk assign, the technician's acceptance (`2.499.0`)

**Built from the images** (B14 rules 42, 44, 37): 02 (Assign in bulk), 12 (Assign a job), 13 (Reassign a job), and for P4.1 — which no image draws — 01 and 03 under rule 44. Judgments in the decision log row *"CR-168 ROUND 3 · ASSIGN"*. Extends ORDERS-LIST's §11 dialogs; nothing of theirs is rewritten except the `<select>` the advice replaces.

| Task | What landed | Image |
|---|---|---|
| P4.12 | *Assigned to* is a search list (`CandidatePicker`, B14 rule 43, so the raise's crew step can take the same picker): paged `page=1&per=50` and searched on the server from two letters (NFR-3, NFR-5, IS-3); *Best fit* first with its pill; each name with its kind and its advice at the right — *{skill} ✓* or *Missing skill: {skill}*, *Certificate lapsed {date}*, *Same area*, *Off that day*, *N jobs that day*; **no name is ever disabled** (ruling 2). *Advice only — any name can be chosen.* under the field | 12 |
| P4.4 (screen half) | On a held job, choosing someone else: *Was D. Ortiz. R. Patel · …* under the field and *Why it moves* — five drawn reasons and a note, required; sent as `reason` on `PATCH /work-orders/{id}/edit` in the dispatcher's words. The effects box's audit line now names the reason | 13 |
| P4.13 | *Assign N orders* offers the UNION of the ticked orders' candidates (the intersection retired with `BR-WRK-029`), each with the advice across all of them, and one line: *Advice: 1 lacks a needed skill. Off that day: M. Chen.* (or *All 5 have Meter I.* when every page has been seen) | 02 |
| P4.1 | *Accepted* · *Not accepted yet* · *Declined* under the technician on Orders and after the name on the order's line — from SRV-1's `technician_acceptance` | 01, 03 |
| P1.27 (order page) | *Assign…* on a job nobody holds, *Reassign…* once somebody does | 03 |

**Contract read.** `GET /work-orders/{id}/candidates?q=&page=&per=` in §7.3's envelope; the screen also reads today's `{skill, policy, candidates[]}` (one function, `normaliseCandidates`, to delete once SRV-2's server serves only the envelope). **Appended for SRV-2:** `PATCH /work-orders/{id}/edit` accepts `reason` (text) when the holder moves off somebody onto somebody else; it is carried on both history rows and a reassign without it is refused `work.dispatch.reason_required` — the edit page is where a reassign is saved, so §7.3's `POST …/assignments act: "reassign"` alone would never see image 13's reason.

**Tests:** `07-frontend/src/features/work/cr168Assign.dom.test.tsx` — 19 cases, 17 red on `42447ed6a` before the build (2 were already true: the title counts the orders, a held job reads *Reassign…*), all 19 green after. ORDERS-LIST's `cr168OrdersList.dom.test.tsx` now picks a name the way a dispatcher does (open the list, press the name) instead of `selectOptions`; `OrdersPage.test.tsx`'s intersection case is replaced by the union case it now contradicts; `OrderDetailPage.dom.test.tsx` mounts image 03's held job. **Version** `2.499.0`. **Rollback:** redeploy `2.498.0`; no migration, no stored data change.

### 13.1 · The order page re-shot on SRV-1's server (`2.499.1`)

`10-scripts/cr168_order_page_seed.py` re-run (it now looks up W-5000, `AC-2026-00001` and Unit 1 by the
numbers a person reads — its literal uuids refused on a fresh build) and `cr168_order_page_walk.mjs` re-run,
PostgreSQL 16 `sbh_wmap2`, Chromium 1440, as Dana. **The first walk found the page CRASHING on both jobs**
(*Unexpected Application Error!*, React error #31 on `{id, label}`) — the server serves `location.unit`
as a record and the screen printed it (`DEF-WRK-9600`) — **and *Put on hold…* offering no reason**
(`DEF-WRK-9601`: the client kept rows whose `active` is true, a flag the server never sends). Both filed
first, each proved red by giving the screen's test fixture the SERVER'S shape, then fixed on the screen.

| Image | Now shows | Photograph |
|---|---|---|
| 03 | Meter W-5000 · Unit 1 · Holder Ana Alvarez · Phone +1 (402) 555-1000 · header line with the unit | `after/03-order-overview-not-completed.png` |
| 04 | the same, plus Closed by D. Ortiz, and the signature panel with the mark, Signed by Ana Alvarez, When, Taken by D. Ortiz | `after/04-order-overview-completed.png` |
| 10 | Reason offers Weather · Waiting for a part · Customer not home · Access refused · Other | `after/10-order-put-on-hold.png` |

Still a dash, and each is DATA rather than wiring: *Service* (the seeded jobs carry no service), *Due*,
*Gate code*, *Access notes* (none recorded on Unit 1). The window reads 04:00–07:00 because the seed books
09:00 in the container's UTC, which is 04:00 in the utility's zone. `DEF-WRK-9581` closed.

**Second push (`2.501.1`), on SRV-2's server (`2.500.0`/`2.500.1`).** The screens read the paged envelope only (the old `policy`/`candidates`/`eligible`/`lapsed` keys are read by nothing — SRV-3 may remove them); a crew's `members` reads *2 people*; a held job taken to *Nobody yet* asks *Why it moves* (`DEF-WRK-9607`, SRV-2's judgment (6) refuses any move off a holder without a reason); the bulk dialog asks one reason when any ticked order is held and sends `reason` on `POST /work-orders/bulk`; the picker reopens on a click (`DEF-WRK-9608`, a kit fix in `RemoteSearchSelectField`). Unowned red read and filed: `DEF-WRK-9609` (`usEnglishCatalogue.test.ts`, *Tick* in `work.raise.selection_empty`, red since `6d428bb13`). Tests: `cr168Assign.dom.test.tsx` 22 cases — the two defect cases red before their fixes, all green after; the hand-typed old-shape case is replaced by one drawn from SRV-2's recorded answer.

**After-walk on PostgreSQL 16 (`sbh_wassign`, seeded demo, 1440)** — `10-scripts/cr168_assign_walk.mjs` after `10-scripts/cr168_assign_walk_prep.py` (takes WO-0027, Water I, off D. Ortiz by the dispatcher's own unassign act). 12 checks, all PASS: on WO-0027 every one of eight names is offered and none disabled; **M. Chen (no Water I) reads *Missing skill: Water I* and is assigned — the server answered 200**; **J. Okoro (certificate lapsed 2026-09-22) reads *Certificate lapsed 09/22/2026* and the reassign to him with *Workload — M. Chen has four jobs that day.* is accepted (200)**; a reassign without a reason is stopped on the page; *Assign 2 orders* (WO-0016, WO-0022) offers everybody and reads *Advice: 3 lack a needed skill.*, then *Advice: M. Chen · Missing skill: Water I.* once chosen. Photographs (each opened, none blank): `08-qa/work-2026-10-04/after/12-orders-assign-a-job-assign-advice.png`, `13-orders-reassign-a-job-assign-advice.png`, `02-orders-assign-in-bulk-assign-advice.png`, `02b-orders-assign-in-bulk-chosen-assign-advice.png`. Writes the walk makes: WO-0027 assigned to M. Chen, then reassigned to J. Okoro with that reason.

## 15 · Round 3 — lane SRV-2: the raise and the assign server (`2.500.0`)

**Built** (server only; the screens are RAISE's and ASSIGN's, building against these routes in parallel): P2.5,
P2.9–P2.14, P2.16 (the read RAISE draws), P2.17, P2.20, P2.21, the bulk raise, candidates paged and uncapped, P4.4–P4.6,
P4.14; P4.8 needed nothing (P0.2 did not slip — `metering/0071`, SRV-1). Judgments: decision log *"CR-168 ROUND 3 ·
SRV-2"*; additions to the contract: §7.3 appendix below.

| Task | What a user gets | Where |
|---|---|---|
| P2.5 · ruling 25 | `POST /work-orders` takes `assignee {technician_id\|crew_id}`, `window_start`/`window_end` and `due_on`; the order and its assignment commit together, the phone is told after | `work/raise_svc.py`, `work/dispatch.py` |
| P2.5 | `GET /work/candidates?template_id=&premises_id=&unit_ids=&on=&q=&page=&per=` — the advice before the job exists | `work/raise_svc.py`, `work/advice.py` |
| P2.9 | the five step-2 fields write existing columns (priority, due date, notes) and two acts (assign, schedule) | `work/raise_svc.py` |
| P2.11 | a water template on an electric job or meter is refused `work.order.template_wrong_service` | `metering/connections.py` |
| P2.12 · ruling 19 | `POST /work-orders/bulk-raise` — one job per unit (per asset when an asset type is chosen), one savepoint per job, an answer per job, a repeated key returns the first answer | `work/raise_svc.py`, `work/0032`, `work/0033` |
| P2.13 · `DEF-WRK-9527` | Unit 205 of 500 Main St on a 12 Kestrel Park job is refused `work.order.unit_not_on_premises` | `metering/connections.py` |
| P2.14 · `DEF-WRK-9528` | a *per unit, water* template raises a per-unit water job (scope and service copied); an asset outside the template's types is refused `work.order.asset_type_not_on_template` | `metering/connections.py` |
| ruling 20 | an asset type named with no asset is refused `work.order.asset_required` | `metering/connections.py`, `work/raise_svc.py` |
| P2.16 · ruling 22 | `GET /work/raise/assets?unit_ids=&asset_type=&service=&q=` — the assets on the ticked units, searchable by asset no, serial and where, `shares_unit` for image 15's *Choose one* | `work/raise_svc.py`, seams |
| P2.17 | the Area chip finds a job by its building's area (walked), not by a column nothing wrote | `work/dispatch.py` |
| P2.20 | a job raised on an asset (or a unit) says where it is — premises, unit, service walked | `metering/connections.py` |
| P2.21 | an asset is offered only its own service's templates, paged in SQL | `work/raise_svc.py`, `work/api.py` |
| P4.12 · `DEF-WRK-9531` | `GET /work-orders/{id}/candidates?q=&page=&per=` — every technician, crew and contractor, paged in SQL, no maximum | `work/advice.py` |
| P4.5 · `DEF-WRK-9533` | advice beside each name (`skill`, `has_skill`, `area_match`, `off_that_day`, `jobs_that_day`, `certifications_lapsed`) and one `best_fit`; nothing is refused; `block` retired (`work.settings.lapse_policy_retired`) | `work/advice.py`, `work/dispatch.py`, `work/workforce.py` |
| P4.6 🔒 | an assignment against the advice writes `work.order.assigned_against_advice`; the history marks the line | `work/dispatch.py`, `work/edit.py` |
| P4.4 | reassign = one request, two rows sharing a reason and an `act_group`, at both doors (`act: reassign` and `PATCH …/edit` with `reason`); refused `work.dispatch.reason_required` without one | `work/dispatch.py`, `work/edit.py` |
| P4.14 | `POST /work-orders/{id}/send-back {reason}` — a finished job back to the field; refused `work.order.already_accepted` once accepted | `metering/connections.py`, `work/api.py` |

**Appended to §7.3 by lane SRV-2, each with its reason:**

| Added / moved | Where | Why |
|---|---|---|
| candidates also carry `skill`, `on`, and for ONE round `policy` + `candidates` (= `results`) and per row `lapsed` + `eligible: true` | `GET /work-orders/{id}/candidates` | today's edit page and bulk-assign dialog read them; ASSIGN moves to `results`/`advice` and the keys go in that commit |
| crew and contractor rows add `members` (counted) | candidates | image 16's *2 people* |
| bulk-raise results add `unit {label}`, `asset {asset_no}`; the answer adds `replayed` | `POST /work-orders/bulk-raise` | image 18's Unit and Asset columns; a screen can say the press was already answered |
| `idempotency_key` is REQUIRED (`work.raise.key_required`) | bulk raise | a bulk write without one can raise every job twice |
| raise-assets rows: `{id, asset_no, serial, location, type {id,name}, service {code,name}, unit {id,label}, premises {id,address}, shares_unit, last_read {reading, unit, on}\|null}` | `GET /work/raise/assets` | image 15's *Choose one* and LAST READ (lane RAISE); `last_read` is the latest ACTUAL reading — an estimate is skipped; `asset_type` is the asset-types row id |
| `asset_type_id` on `POST /work-orders` and the bulk raise | the raise | ruling 20 binds when the raise NAMES a type (judgment 8) |
| `due_on` (a date) beside `due_at` | the raise | ruling 23's date picker; stored as the end of that day locally (judgment 5) |
| `reason` on `PATCH /work-orders/{id}/edit` | `work/edit.py` | lane ASSIGN saves image 13's reassign there |
| asset templates: the house envelope + `asset` (+ `service_code`) + `rows` twin for ONE round | `GET /assets/{id}/work-order-templates` | the asset door reads `rows` today; RAISE retires it (ruling 35) |
| `GET /work/templates` adds `f.job_type` (a kind or its heading), `f.asset_type` (naming it, or naming none), `f.scope`, `f.raisable=1` (active + published) | `work/selectors.py` | the raise's step 1 (lane RAISE); the list's own SQL paging stays SRV-3's (P3.5) |
| `send_back` needs a `reason` (`work.order.send_back_reason_required`) | send back | the field must be told why |

**Migrations, up → down → up on PostgreSQL 16** (`sbh_wsrv2`): up applied `work.0032_cr168_bulk_raises` and `work.0033_rls_force_bulk_raises` OK; `migrate work 0031` unapplied both OK and `to_regclass('work_bulk_raises')` read NULL (the table gone); up again applied both OK; `pg_class` reads `work_bulk_raises | t | t` (ENABLE + FORCE).

**Proved on PostgreSQL** (`tests/test_cr168_srv2_bulk_raise_pg.py`): 12 passed with `tests/test_us_wrk_025_dispatch_pg.py` (the append-only trigger untouched). Three units, the second refused BY THE DATABASE (a duplicate key row issued with a cursor) → units 1 and 3 raised, the answer `[ok, refused, ok]`. **Red first (law 7):** with the per-job `transaction.atomic()` removed, the same case fails `psycopg.errors.InFailedSqlTransaction: current transaction is aborted, commands ignored until end of transaction block`; restored, green. The same key pressed twice → 3 jobs, not 6; a second tenant reads none of `work_bulk_raises` under the probe role.

**Defects closed:** `DEF-WRK-9527`, `9528`, `9531`, `9533` — their held cases released (no held case is left in
`tests/test_cr168_round1_held_defects.py`). `US-WRK-025` TC-3 and `US-WRK-020` TC-3 (the block side) rewritten to the
rulings with their citations.

**Rollback:** redeploy the previous build to take the behaviour back — the skill refusal returns (against ruling 2) and
the bulk raise and send-back disappear; to take the schema back too, `migrate work 0031` (`work/0033` and `0032` reverse
cleanly; a repeated bulk press after that would raise its jobs again).

### 15.1 · Lane RAISE's last two asks, and the real answers recorded (`2.500.1`)

`GET /units` takes `f.unit_type` (any of the unit-type codes; a SQL narrowing, so the list still pages in SQL) for
image 14's *Residential · Commercial* chips. `10-scripts/cr168_srv2_record_shapes.py` calls each SRV-2 route through
its view on PostgreSQL 16 (`sbh_wsrv2`, `seed_demo` + `load_sample_data --tenant brazosbend`) as Dana and writes the
answer to `07-frontend/src/features/work/__fixtures__/`: `work-order-candidates`, `work-raise-candidates`,
`work-raise-assets`, `asset-work-order-templates`, `work-templates-for-the-raise`, `work-orders-bulk-raise` — six
recorded (send back records only where the demo holds a finished job nobody has accepted; on this demo it held none).
Lane SHAPE-SWEEP's generator picks them up. **Rollback:** redeploy `2.500.0`; the chips then narrow nothing.

## 16 · Round 3 — lane RAISE: the raise on units, in bulk, and its two filled doors (`2.501.0`)

**Built from the images** (B14 rules 42, 44, 37, 21, 31, 33; ruling 16 — a step flow keeps its footer): 14 (raise on units), 15 (an asset type chosen), 16 (Schedule & crew), 17 (Confirm), 18 (Result), 19 (from an account), 20 (from an asset). Rulings 19–25 and 35 built. Judgments: decision log *"CR-168 ROUND 3 · RAISE"*.

| Task | What landed | Image |
|---|---|---|
| P2.2 · `DEF-WRK-9572` | Step 1 is Premises (a dropdown you type into, server-searched from two letters, the building's type and unit count beside each and under the choice — ruling 21), Units, Job type, Template, Asset type, Priority, Description, and the line *Raises N jobs — one per unit.* Continue names each missing field under itself | 14 |
| P2.15 | The building's units as a table you tick — search, the tenant's unit-type chips (`f.unit_type`), *N of M chosen*, tick-all for the page, paged on the server (`GET /units?f.premises_id=`); one job per unit ticked (ruling 19) | 14 |
| P2.16 | Asset type: set by the template where it names one, else *None — the unit itself*. Once chosen, the ticked units' assets with their own search (ruling 22); a unit with two of the type reads *Choose one* and Continue refuses *Choose an asset for Apt 101.* until one is ticked (ruling 20); one job per asset | 15 |
| P2.3 (raise half) · `DEF-WRK-9582` | Job type is a two-level picker: a heading with sub-types is a group, its sub-types the options | 14 |
| P2.18 | Step 2: Due date (a date picker opening on the priority's promise — ruling 23), Visit (date + window, *What the customer is told.*), *Assign to* — every technician, crew and contractor, best fit first, advice beside each, or *Nobody yet* (ruling 25; ASSIGN's `CandidatePicker` over `GET /work/candidates`). **No Area** (ruling 24) | 16 |
| Confirm · Result | The summary, *The jobs* table, the EFFECT box, *Back · Raise N jobs ✓*; then *N jobs raised* with each job's number and *Raised* / *Not raised* and why, *Raise more* · *Open work orders* | 17, 18 |
| P2.4 · `DEF-WRK-4752` | `/{tenant}/accounts/{id}/work-orders/new` — *From the account* (Account, Where, Category, Status, Services), then Job type, Template, Asset type and the account's assets; the account's *⚡ Raise work here* opens it, and a premises' opens the raise with the building picked (`?premises=`) | 19 |
| P2.19 | The asset's *Raise work order* (same address, `BR-WRK-056` holds) opens the three steps *From the asset* (Asset, Service, Where, On site, Account); figure 42's one-page form is retired (ruling 35) | 20 |

**The write.** Every door makes one `POST /work-orders/bulk-raise` (§7.3), even for one job, carrying `type_id` + `type`, `asset_type_id` when an asset type is chosen (ruling 20), `account_id` (account door), `source` (`assets` on the asset door) and `custom_data` (§5.7 N4 — the utility's own fields stay on step 1 under Description) — all accepted by SRV-2 (`2.500.0`). Templates are read with `f.job_type` and `f.raisable=1`; the assets with the template's `service`; *Choose one* reads SRV-2's `shares_unit`. **The asset door reads the templates envelope's `results`, never the one-round `rows` twin, so SRV-2 may retire it.** Tests use SRV-2's recorded PostgreSQL answers (`features/work/__fixtures__/*.recorded.json`); the premises picker, the units page and a template's detail have no recording and are written in the server's shapes.

**Not built here, and why:** `DEF-WRK-9582` stays OPEN for its other pickers — the Orders type filter, the edit page and the template builder are other lanes' files this round.

**Tests:** `features/work/raise/cr168Raise.dom.test.tsx` (9 cases; the first 8 written red-first — all 8 red on the tip before the build), `cr168RaiseAccount.dom.test.tsx` (2), `raiseModel.test.ts` (7); door tests in `buildViews.test.tsx` and `buildViewsWorkOrders.dom.test.tsx` red on the tip before the fix; `features/assets/RaiseWorkOrder.test.tsx` rewritten for the retired form (the empty-template refusal kept). **Version** `2.501.0`. **Rollback:** redeploy `2.500.1`; no migration and no stored data change.

**After-walk (`2.503.1`, PostgreSQL 16 `sbh_wraise`, 1440):** `08-qa/work-2026-10-04/after/` — `14`, `15`, `16`, `17`, `17b`, `18`, `18b`, `19`, `19b`, `20`, `20b` (each opened, none blank) with `RAISE-side-by-side.md`; script `10-scripts/cr168_raise_after_walk.mjs`. Raised on PostgreSQL: one job on one unit, a bulk raise of six jobs on six units (one per meter, assigned), one from an account, one from an asset — read back from `work_orders`. The walk found `DEF-WRK-9616` (tick-all chose only the last row — this lane's, fixed in `2.503.1`, red test first) and `DEF-WRK-9612` (the server's `f.job_type` drops every untyped template — filed and fixed by lane SRV-3 in `2df8a4cfe`; the raise sends `f.job_type` again and the walk was re-run on it)` in `raiseEndpoints.ts`). `DEF-WRK-9609` (*Tick* in the US catalogue) fixed in the same push. `DEF-WRK-9572` and `DEF-WRK-4752` closed (fixed in `cfa32c531`).

## 16 · Round 4 — lane SRV-3: the Crews and Templates server (`2.502.0` crews)

**Built in `2.502.0`** (server only; the screens are CREWS's): P3.4, P3.44, P3.46, P3.52, P3.53 (served — the
columns are SRV-1's `work/0028`), the P3.45 read, ruling 26 (add crew member). Judgments: decision log *"CR-168
ROUND 4 · SRV-3"*. P3.23's two crew indexes are SRV-1's `work/0031`, and the three lists now use them.

| Task | What a user gets | Where |
|---|---|---|
| P3.4 · ruling 30 | `GET /work/crews?view=technicians\|crews\|contractors&q=&sort=&page=&per=` — one queryset per list, `ORDER BY … LIMIT/OFFSET`, `counts {technicians, crews, contractors}` by `COUNT(*)`; sorts `name` (all), `crew` (technicians), `members` (crews, contractors); search matches name, skill and crew | `work/workforce.py` |
| P3.53 | contractor rows carry `phone`, `email`; add/edit write them; a crew sending one is refused `work.crew.contact_contractor_only`, a malformed email `work.crew.email_format` | `work/workforce.py` |
| P3.44 | `PATCH /work/technicians/{slug} {crew_id}` moves a technician (null = no crew), audited `work.technician.crew_moved` with both crews' names; `members` is counted — *D. Ortiz moved to Field crew B; Field crew A reads (1)* | `work/workforce.py`, `work/api.py` |
| P3.52 | `PUT /work/crews/{id}/skills {skills[] {skill_id, proficiency}}`, a replace, audited `work.crew.skills_set` — Field crew C with Water I is advised for a Water I job | `work/workforce.py` |
| ruling 26 | `POST /work/crews/{id}/members {technician_id}\|{user_id}` — answers the crew with its counted `members`; a contractor is refused `work.crew.members_crew_only` (ruling 36's logins wait for the field-app document) | `work/workforce.py` |
| P3.46 | `GET /work/technicians/{slug}` adds `crew {id, name}` (was a bare name), `today {jobs, on}`, `this_month {month, closed, on_time, on_time_of, first_visit_pct, vs_estimate_pct, vs_estimate_minutes}`; `UNSERVED_UNTIL_WAVE_G` retired; `GET …/performance?period=&page=&per=` — `tiles` + `by_job_type` rows grouped and paged in SQL | `work/technician_figures.py` |
| P3.45 (read) | `GET /work/technicians/{slug}/jobs?f.state=open\|done&q=&page=&per=` — every job held or once given (an assignment row names them), newest first, each the dispatcher's row plus `still_holds` | `work/technician_figures.py` |
| twins | SRV-2's `policy`/`candidates`/`eligible`/`lapsed` and the asset templates' `rows` removed (ASSIGN 2.501.1, RAISE 2.501.0 confirmed; front end grepped at `3646d5343`: `AssetTemplatesPayload` now types `results`) | `work/advice.py`, `work/dispatch.py`, `work/api.py` |

**Appended to §7.3 by lane SRV-3, each with its reason:**

| Added / moved | Where | Why |
|---|---|---|
| crews rows: technician `crew {id,name}`, `email`; crew/contractor `members`, `active`; contractor `phone`, `email` | `GET /work/crews` | images 25, 27, 28 draw a technician's Crew, a crew's Members and a contractor's contact |
| no `view` → the one-table answer + `counts.rows`/`people`, ONE round | `GET /work/crews` | the screen at the tip reads it until lane CREWS lands (judgment 3) |
| `today.on`, `this_month.month`, `this_month.vs_estimate_minutes` | technician detail | image 31's *Avg vs estimate −4 min* is minutes; the dates say which day and month were counted |
| `still_holds` on a job row | `…/jobs` | a job moved away stays listed and says so (judgment 1) |
| crew writes answer the full list row | `POST/PATCH /work/crews`, `…/skills`, `…/members` | the add forms redraw from the answer without a second read |

**Defects filed:** `DEF-SRC-9610` (a search-suite case red on the tip before this lane, dated in a clean worktree at
`3646d5343` — not this lane's to fix). **Rollback:** redeploy `2.501.1`; no migration in this build.


## 17 · Round 4 — lane SHAPE-SWEEP: every Work read the back office draws, recorded and checked (`2.502.1`)

**Why.** `DEF-WRK-9600` and `DEF-WRK-9601` reached a walk on the real server with every test, `tsc` and
gate green, because both sides tested against fixtures their own lane typed (`DEF-WRK-9606`). §7's new
rule above is the fix; this section is the sweep that applied it.

**How it was measured.** PostgreSQL 16 `sbh_wshapes`: `migrate` + `seed_demo` + `load_sample_data
--tenant brazosbend` + `cr168_order_page_seed.py` (WO-0041 open at Unit 1 / meter W-5000, WO-0042
completed and signed) + `cr168_orders_list_walk_prep.py`; `runserver` on the tip (`2.502.0`, SRV-3's
server); signed in as Dana. `cr168_capture_work_shapes.py --prepare` held WO-0022 through the real
`POST …/hold` (Weather) and recorded **49 reads of 31 endpoints, all 200**, into `__fixtures__/server/`
with a `manifest.json`. Each recording, and SRV-2's five read/raise recordings, was assigned to the type the
screen reads it through (`Wire<T>` widens literal unions only) — 49 checks — and the screens were mounted
on them (19 cases). The sweep was run twice: first on `2.500.1`, then again after SRV-3 landed `2.502.0`
mid-sweep, which is how `DEF-WRK-9611` was found within the hour it was introduced.

| Endpoint | Mismatches found | Fixed where |
|---|---|---|
| `GET /work-orders` (open, and `status=complete`) | none | — |
| `GET /work-orders/awaiting-approval` | none | — |
| `GET /work-orders/{id}` (open at a unit · held · completed and signed · accepted) | `location.unit` object read as text — `DEF-WRK-9600`, fixed in `2.499.1`; now held by `tsc` and a render | (screen, `2.499.1`) |
| `GET /work-orders/{id}/audit` · `/checklist` · `/attachments` · `/close-readiness` · `/signature` | none (`/signature` on an unsigned job answers an empty body, recorded as `null`) | — |
| `GET /work-orders/{id}/edit` | **`technician_id` typed REQUIRED, never served** — the server serves `technician {id, kind, name, slug}` (§7.3); the page worked only through its fallback and every edit-page fixture typed the field — `DEF-WRK-9605` | screen type `OrderEditForm`, optional |
| `GET /work-orders/{id}/candidates` | none (the paged envelope with advice) | — |
| `GET /work-orders/map` | none | — |
| `GET /work/hold-reasons` | `active` absent, screen kept only `active: true` — `DEF-WRK-9601`, fixed in `2.499.1`; held | (screen, `2.499.1`) |
| `GET /work/technicians/{slug}` | **`crew` typed as a name; since `2.502.0` it is `{id, name}`** (§7.3). Nothing draws it yet, so nothing crashes today — the first line that prints it would have crashed the page as `DEF-WRK-9600` did — `DEF-WRK-9611` | screen type `TechnicianDetail`, `{id, name} \| null` |
| `GET /work/crews` (three views) · `/work/crew-directory` · `/work/certification-watch` | none against the screens | — |
| `GET /work/raise-options` · `/work/kpis` · `/work/areas` · `/custom-fields?entity=work_orders` | none | — |
| `GET /work/parts` · `/work/parts/issues` | none | — |
| `GET /work/templates` · `/work/templates/{id}` · `/versions` · `/usage` · `/work/template-packs` | none | — |
| `GET /work/rules` · `/work/labour-rates` · `/work/performance` | none | — |
| SRV-2's recordings: candidates, asset work-order templates, templates for the raise, raise assets, bulk raise | none against `CandidatePage`, `AssetTemplatesPayload`, `TemplateList`, `RaiseAssetRow`, `BulkRaiseOutcome` | — |

**Where the server and §7.3 still differ, and the screen agrees with the SERVER** (nothing breaks; each is
the server lanes' to close or §7.3's to amend, so each is stated rather than changed here):
`GET /work/hold-reasons` sends no `active` (§7.3 names it; MAP2 ruled the screen keeps a row unless it says
`false`) · `GET /work-orders/{id}/audit` still serves the `rows` twin beside `results`.

**Served and read by no screen yet** (unbuilt reading, not a shape fault): list rows' `hold`, `accepted`,
`sla`; the detail's `sla` and `timeline`; the edit form's `appointment` (the utility's time zone) and
`priorities`; a technician's `today` and `this_month`; a crew row's `crew`, `members`, `phone`, `email`;
a template's `est_duration` (a raw duration string beside `est_duration_minutes`) and `updated_at`; an
attachment's `duplicate`.

**Blind spots, counted (law 7): shapes no recording carries, so only `tsc` against the code's type covers
them.** Of the 42 orders recorded, the technician's acceptance is only ever `pending` or `null` — 0
`accepted`, 0 `declined`; 0 part issues; 0 attachments on an open, held or accepted job; 0 unplaced map
pins; 0 technicians `unavailable`. A later seed that produces any of them is a re-run of the recorder, not
a new test.

**Red first.** `tsc` on the recordings, before each fix: `Property 'technician_id' is missing … but
required` (`DEF-WRK-9605`) and `Types of property 'crew' are incompatible` (`DEF-WRK-9611`). The guard was
also proved able to fail on the two defects it exists for, by putting `2.499.0`'s code back for one run:
the DOM suite went 4 red (*Objects are not valid as a React child (found: object with keys {id, label})* on
every order page; `expected [] to deeply equal [ 'Weather', … ]` for the hold reasons) and `tsc` named the
hold-reason recording and both order recordings; restored, 19 of 19 green and `tsc` clean.

**Rollback.** Redeploy `2.502.0`. Only two types and test files change; no screen behaves differently and
no data moves.

## 18 · Round 4 (brought forward) — lane PARTS: Parts and Import parts (`2.503.0`)

**Built from images 35–42** (B14 rules 42, 44, 37, 21, 31, 33, 2; rulings 16, 29, 32, 33), PO *"Yes start
it"* bringing R4 PARTS forward. Judgments: decision log *"CR-168 ROUND 4 (BROUGHT FORWARD) · PARTS"*.
Side by side: `08-qa/work-2026-10-04/after/PARTS-side-by-side.md`.

| Task | What a user gets | Where |
|---|---|---|
| P3.8 · `DEF-WRK-9578` | a pencil on every row opens *Edit a part* — the Add form filled with the part (`92.4000` opens as `92.40`) and *Save part ✓* | `AddPartModal.tsx`, `PartsPage.tsx` |
| P3.9 · `DEF-WRK-9579` | *Retire part* asks first (danger tier, *Crews can no longer pick it. Past jobs keep it.*); an inactive part shows *Reactivate part*, one press | `PartsPage.tsx`; `work/services._clean_part` takes `active` on an edit |
| P3.10 · `DEF-WRK-9580` | *+ Filter* — Category (the tenant's own, and *No category*), Unit (the register's own words), Status | `PartsPage.tsx`; `work/selectors.parts_page`, `part_units`; `work/api.parts` |
| P3.11 · `DEF-WRK-9574` | *Issue log* opens the log: When · Part # · Name · Quantity · Issued to · Job · Purpose, newest first; the hold test is now the hold's expiry test | `PartIssueLog.tsx` (new, rule 43) |
| P3.50 · P3.54 · `DEF-WRK-9585` | *Name* on the form, the column and the search box; refusals *This is required.*, *Unit cost must be a number.*, *Keep unit cost to 4 decimals.*; the drawn help lines and *Add part ✓* | `AddPartModal.tsx`, eleven catalogues |
| P3.55 · `DEF-WRK-9587` | the import keeps the category, by name or code; an unknown category is rejected at Validate instead of loading blank | `metering/import_runs.LOOKUP_INDEX_BUILDERS`, `metering/import_rules._eval_category_in_lookup` |
| P3.56 · `DEF-WRK-9588` (+ `DEF-521`) | stage 2 shows a sample value per column (every target) and *Rows forward* reads the rows in until the transform answers; *Every part needs a name.*; the KEY column names the part; *Add how it is counted — each, ft, roll.*; *Import it as Insert & update. Or take the row out.*; *Insert new only* no longer sends a parts file to numbering | `metering/import_runs.extract` (`samples`), `source_key`; `metering/import_rules`; `ImportWorkflowPage.tsx` |

**§7 items this lane took from SRV-3** (SRV-3 had not started; each is Parts-only): edit and retire a part
(`PATCH /work/parts/{id}` + `active`), the register's filters paged in SQL (NFR-3/5), and P3.55, the import
keeping the category (`DEF-WRK-9587`). **Appended to §7.3 by lane PARTS:** `GET /work/parts` accepts
`f.category` (a category CODE, or `none`; several comma-separated), `f.unit`, `f.status` (`active` |
`inactive`), and returns `units` (the register's distinct units) beside the page; `PATCH /work/parts/{id}`
accepts `active` (boolean; refused on `POST`, refused as `work.parts.active_yes_no` when not a boolean);
`POST /imports` (extract) returns `samples {header: first non-empty cell}`, none for an identity column.

**Proof.** pytest `tests/test_cr168_parts.py` — 15 cases; **12 red on `72e94b365`** (a clean worktree at the
tip, before any change), 3 already true there (edit of name/cost, a non-boolean `active` refused as an
unknown field, the dry run writes nothing), all 15 green after, on SQLite and on PostgreSQL 16. vitest
`PartsPage.dom.test.tsx` (10, new) and `PartsPage.test.tsx` (10, two rewritten) — **12 red at the tip, 20
green after**; tsc clean (and shown able to fail). Browser: `10-scripts/cr168_parts_after_walk.mjs`, 22 of 22
checks on PostgreSQL at 1440 — a duplicate refused naming the part, an edit saved, a retire, two filters,
the Issue log, and the round-1 file through all five stages with **the dry run leaving the register at 10
parts** and **the load writing MTR-W34 as *Meters***. Fourteen photographs in `after/` (taken on the build before its number moved to `2.503.0` at push — the footer reads `v2.501.0`; the code is the same) (35, 35b–e, 36,
36b, 36c, 37, 38–42).

**Reds read and not caused here:** `test_us_wrk_007_tc2` (seeded types now carry a default priority) — red
on the clean tip, filed `DEF-WRK-9613`; ten cases in `test_cr023_import_stages.py` and
`test_def_met_5802_declared_columns.py` — identical on the clean tip, already `DEF-MET-9268`'s.
**Found on the walk, filed, not fixed:** `DEF-MET-9614` (a second commit of the same file answers 500),
`DEF-SHL-9615` (a server refusal stays under a retyped field).

**Defects closed:** `DEF-WRK-9574`, `9578`, `9579`, `9580`, `9585`, `9587`, `9588`, `DEF-521`.
**Rollback:** redeploy `2.502.0`. No migration and no stored data change; parts edited, retired or
imported under `2.503.0` read correctly under `2.502.0`, which simply offers no edit, filter or Issue log.

**Follow-up `2.503.2` (`DEF-WRK-9617`):** the coordinator found `usEnglishCatalogue.test.ts` red on `368d908d7` — the
US English catalogue carried the drawing's British *metre* in Add part's help line; it reads *meter*. The other
ten catalogues keep their own words. From now on this lane runs `src/i18n` with every copy change.

## 16 (continued) · lane SRV-3

### 16.1 · `2.502.2` — the raise offers untyped templates; the templates list in SQL

`DEF-WRK-9612` (filed by SRV-3 for lane RAISE's report; the id RAISE first used, `9611`, was SHAPE-SWEEP's):
`f.job_type` now keeps templates naming NO job type, as `f.asset_type` keeps those naming none — all 6 of 6 demo
templates are untyped and the raise had offered none. Red first: `assert {'Typed one'} == {'Typed one', 'Untyped
one'}`. P3.5: `templates_page` counts the footer with one aggregate and reads a page in one query with its five
contents counted as subqueries (≤ 4 queries per call, asserted). Fixed in `2df8a4cfe`, closed in `8eae63356`.

### 16.2 · `2.504.0` — the Templates server

| Task | What a user gets | Where |
|---|---|---|
| PO answer 3 | task rows carry `instruction` (text\|null) on `GET /work/templates/{id}` and `PUT …/tasks`; COPIED at the raise onto `work_order_tasks.instruction` (`work/0034`) and served on `GET /work-orders/{id}/checklist` | `work/templates_svc.py`, `work/selectors.py`, `work/order_copies.py`, `work/checklist.py` |
| ruling 6 · P3.25 (server) | help kind `link` (`https` only, `work.template.help_link_https`); help rows serve `{seq, kind, label, ref, url, link}` + `file {id, name, content_type, bytes}` for a stored document; the phone's help row opens a link (`mobile._help_row`) | `work/0034`, `work/templates_svc.py`, `work/selectors.py`, `work/mobile.py` |
| P3.14 | `POST /work/templates/{id}/help/upload-url {filename, content_type}` → `{upload_url, method, field, max_bytes, content_types}`; `POST …/help/documents` (multipart `file`, PDF/PNG/JPG ≤ 10 MB) → `{id, ref, name, content_type, bytes, url}`; `GET …/help/documents/{doc}/content` same-origin bytes, `private, no-store` | `work/template_help.py`, `tenancy/0059` |
| P3.28 | `GET /work/templates/{id}/audit?page=&per=` — `{at, by {name}, act, collection, version, summary}` newest first, paged in SQL. ⚠ The Audit tab's *"opens with the next release"* sentence is lane TEMPLATES's to delete, with its test, in the commit that reads this | `work/template_history.py`, `work/seams/audit_seam.py` |
| P3.47 | a raise from a template is planned at the sum of its task minutes; `metering/0073` back-fills orders from their own copied tasks (4 of 40 on the demo) | `metering/connections.py`, `metering/0073` |
| P3.22 | nothing left for the server: the asset door's page is the raise (lane RAISE, 2.501.0) and its server half is SRV-2's (P2.19–P2.21) | — |
| P3.23 | the crews indexes are SRV-1's `work/0031`, the templates index `metering/0071`; the three crew lists and the templates page now order by them | — |
| P3.55 | built by lane PARTS (`DEF-WRK-9587`, 2.503.0); nothing duplicated | — |
| §7.3 gaps | `GET /work/hold-reasons` rows add `active`; the order history's `rows` twin is gone (the order page reads `results`; the other reader, `getWorkOrderAudit`, was dead and is removed) | `work/dispatch.py`, `work/api.py`, `workEndpoints.ts` |

**Migrations, up → down → up on PostgreSQL 16** (`sbh_wsrv3`, seeded brazosbend): up printed *40 order(s) with no
estimate read, 4 given the sum of their own task minutes*; down (`metering 0072`, `work 0033`, `tenancy 0058`) left
no `work_order_tasks.instruction` and the help CHECK at three kinds; up again: four kinds, *36 read, 0 given*
(idempotent). Review-ledger rows for all three.

**Recorded from the real server** (`10-scripts/cr168_capture_work_shapes.py`, extended with
`work.technician.jobs`, `work.technician.performance`, `work.template.audit`; `10-scripts/cr168_srv3_template_prep.py`
gives the demo's first published template and *Meter exchange — residential* an instruction and a link first):
`work.template.json` carries `instruction` and a `link` help row, `work-order.open.checklist.json` the copied
instruction, `work.hold-reasons.json` `active`. The SRV-2 recordings with retired twins re-recorded
(`work-order-candidates`, `asset-work-order-templates`, `work-templates-for-the-raise`). `tsc` and 754 Work/Assets
front-end tests green on them.

**Defects:** `DEF-WRK-9618` filed and fixed (G7 red on SRV-2's `work/0032`, a missing marker; red `FAIL: …0032_cr168_bulk_raises.py: lacks HUMAN-OWNED marker` → `PASS: 844 guarded file(s) conform`).

**Rollback:** redeploy `2.503.2`; schema back with the three migrate commands in the CHANGELOG.


## §F · Flows that raise work — lane FLOW-MEASURE (measured on `2.503.2` · `45da0db3c`; no product code, no version)

**The PO's question, verbatim (2026-10-04):** *"are you also raising work orders from Move In, New Connect, Move out etc —
and when work orders are completed is the clerk able to see the status update in those requests? How many types of work
order will you test, and when the technician app is not available how will you complete technician work for the time
being?"*

**Scope.** In: all sixteen `work_orders.source` tokens (`metering/connections.py` `WORK_ORDER_SOURCES`, `BR-WRK-024`), the
door that writes each, one job per working door completed **by its technician** and **accepted by the office**, and the
originating record a clerk would look at, photographed before and after. Out: the nightly rule *schedule* (the sweep was
run once by hand, which is its job body), notifications the acceptance sends, cost lines, and the portal at 390px (a
portal request becomes the same service request the office handles). *Say so if that boundary is wrong.*

**How it was measured.** PostgreSQL 16 (`sbh_wflows`: migrate + `seed_demo` + `load_sample_data --tenant brazosbend`),
backend `2.503.2` on :8501, the compose bundle on :5601. Office as Dana; field work as **R. Patel** (field technician)
— **WO-0046 was closed in the field app itself** at 390×844 (`10-scripts/cr168_flows_field_app_walk.mjs`), every other
job through the same field sync API the phone uses (`POST /work/mobile/jobs/{id}/sync`), signed in with
`surface=mobile`. The office never completed anything (ruling 18). Raises through the real HTTP doors; the rules sweep
and the source check through `10-scripts/cr168_flows_rules_probe.py` (PG, rolled back). Photographs:
`08-qa/work-2026-10-04/flows/` by `10-scripts/cr168_flows_walk.mjs` (`-before` / `-after`, every one opened).

### F.1 · The sixteen sources

| # | Source (*Raised by*) | Raises a job today? (door, file:line) | Completes in the field app? | Status flows back to the clerk's record? | Defect |
|---|---|---|---|---|---|
| 1 | `new_connect` | **Yes** — the New Connect commit, `metering/connections.py:5514`; `CON-26-0129` → WO-0044, WO-0045 | Yes (field API) | **Partly.** The build's Work tab counts *2 · 2 done · 0 open* and each row reads *Completed*; the build's own state does **not** move — `CON-26-0129` stays *Requested*, and `CON-26-0126` reads *Partly activated · Waiting on: inspection* with 5 of 5 jobs accepted (`01`, `12`, `12b`) | `DEF-MET-9633` |
| 2 | `move_out` | **Yes** — `customers/services.py:6039` → `work/from_flows.py:681`; MVO-26-0002 → WO-0046, MVO-26-0003 → WO-0053 | **WO-0046 closed in the field app** after its photographs were linked; the meter-exchange job can then **never be accepted** (`work.reading.no_meter_on_order`) | **No** — the move-out record has no visit line at all, before or after acceptance (`02`, `13`) | `DEF-CUS-9628`, `DEF-WRK-9620` |
| 3 | `move_in` | **Yes** — `customers/services.py:6468`; MVI-26-0004 → WO-0047, MVI-26-0005 → WO-0054 | Yes (field API) | **No, and it says the opposite** — *Still owed · Visit: **Not raised*** over a visit raised, done and accepted (`03`, `14`) | `DEF-CUS-9628` |
| 4 | `transfer` | **Yes** — `customers/transfers.py:2576` (inside `POST /transfers/commit`); TRF-26-0001 → WO-0048, TRF-26-0002 → WO-0055 | Yes (field API) | **No** — *Changeover read: **0 raised · 0 done*** after acceptance; the record counts by the sale's uuid, the job carries `TRF-26-0002` (`04`, `15`) | `DEF-CUS-9629` |
| 5 | `reconnect` | **Yes** — `customers/reconnect_read.py:634` (`POST /disconnects/{ref}/reconnect/work-orders`) and `disconnects.py:5677`; DSC-26-0001 → WO-0049, DSC-26-0002 → WO-0056 — raised by API: on all four demo cases the page has **no service rows**, so no screen door | Yes (field API) | **No** — *0 raised · 0 to raise* after acceptance; the read serves `work_order: None` on every row (`05`, `16`) | `DEF-CUS-9630` |
| 6 | `service_request` (+ portal) | **No** — `route` is a RETIRED action (`customers/service_request.py` `RETIRED_ACTIONS`), `POST …/transitions {action: route}` → **409**. An approved request raises a CHILD instead and links it (*Approved → Move-in MVI-26-0001*, `10`) — its visit is then rows 1–5's | n/a | Through the child only; the close-on-accept at `connections.py:7811` can never run | `DEF-WRK-9623` |
| 7 | `meter_read` | **Yes** — `work/api.py:693` (`POST /work/flows/meter-read/raise`, Reads → *Send someone out*); W-7001 → WO-0050, WO-0057 | Yes (field API) | On the meter's *Work & maintenance* tab only; *Raised by* prints the raw key `work.orders.source.meter_r…` (`07`, `11`) | `DEF-WRK-9621` |
| 8 | `failed_outcome` | **Yes** — on Accept of a failed job, `connections.py:7954`; WO-0058 (failed) → **WO-0059** | — | WO-0059 reads *Raised by: work.orders.source.failed_outcome*; WO-0058's page shows *Accepted* and *Not accepted yet* together and does not link its follow-up (`17`, `18`) | `DEF-WRK-9621`, `DEF-WRK-9624` |
| 9 | `dispatcher` | **Yes** — `RaiseWizard.tsx:325` / `workEndpoints.ts:2180` → `POST /work-orders`; WO-0051, WO-0058 | Yes (field API), accepted | The order is its own record; the premises *Work orders* tab lists it (filter *Status: Open* hides it once done — `09`) | — |
| 10 | `assets` (the Assets door) | **Yes** — `RaiseWizard.tsx:325` (asset origin); W-7001 → WO-0052 | Yes; Accept refused `meter_ambiguous` (`OQ-WRK-1723`, OPEN) | Asset *Work & maintenance* tab (`07`) | — (`OQ-WRK-1723`) |
| 11 | `asset_age_rule` | **Writes `assets`, never this token** — the sweep raised WO-0041..0043 from rule *Asset age rule* and stamped `source = assets` (`work/rules.py:327`) | Yes; Accept refused `meter_ambiguous` | Asset *Work & maintenance* tab (`08`) | `DEF-WRK-4096` (open since 2026-09-05, re-measured) |
| 12 | `dunning_auto` | **No** — rule *Disconnect for non-pay* (`payments`) is refused `work.order.source_unknown` (0 subjects on the demo). The disconnect wizard's *Who goes: Work order* rows are **never sent** (`disconnectDraft.ts` `scheduleCutPlanOf`) — read, not pressed | — | — | `DEF-WRK-4096`, `DEF-CUS-9631` |
| 13 | `high_usage_alert` | **No** — rule *Leak investigation* (`reads`): **98 subjects, 0 raised**, every one refused `source_unknown` and logged | — | — | `DEF-WRK-4096` |
| 14 | `billing_exception` | **No** — rule *Read verification* (`billing`) refused `source_unknown` (0 subjects today) | — | — | `DEF-WRK-4096` |
| 15 | `compliance_calendar` | **No** — no code anywhere writes it (grep: the tuple and one catalogue key) | — | — | `DEF-WRK-4096` names it |
| 16 | `payment_received` | **No, by ruling** — `BR-PAY-036`: a payment alone never books a reconnection; the reconnect raise stamps `reconnect` | — | — | none (ruled) |
| — | rule *Move-in / move-out* (`accounts`) | **No** — 1 subject, 0 raised, `source_unknown` | — | — | `DEF-WRK-4096` |

**Measured** (`cr168_flows_rules_probe.py`): of the five rule source modules, `payments`, `billing`, `reads` and `accounts`
are **REFUSED `work.order.source_unknown`** and only `assets` is accepted; `rules.sweep` raised 3 jobs across 6 enabled
rules. The 40 seeded demo jobs carry **no source at all** (*Raised by —* on every one, `DEF-WRK-9627`).

### F.2 · What blocks the field work itself (the PO's last question)

* **The product already has the technician app** — `/{tenant}/work/mobile`, a phone web page (sign-in, Today, the job,
  readings, photographs, signature, close). R. Patel signed in on it and saw his nine jobs (`20`). **That is how field
  work is completed until a native app exists**; the office may not complete a job (ruling 18) and does not.
* **But today it cannot close any demo job by itself** — every one of the six templates has 2–4 *photo required* tasks,
  and the Photographs pane uploads a photo with no task link, so the close stays *2 photographs still needed* after two
  are taken (`21b`, `22a`) → `DEF-WRK-9619`. It closed only after the photos were linked through the field API (`22`).
* **And the server does not hold the same line** — WO-0044 was closed through sync with 3 required photos missing and
  then accepted → `DEF-WRK-9625`.
* **Every customer flow is offered only *Meter exchange — residential*** (no final read, changeover, reconnect or re-read
  template; 30 job types, 6 templates, none linked) → `DEF-WRK-9626` (`DEF-WRK-9612` is its raise-side sibling); a flow's
  meter exchange stands on the account with no meter, so it can never be accepted → `DEF-WRK-9620`. A job raised from
  a **job type row** (*Reading › Re-read*) closes and is accepted normally (WO-0053..0055).
* Flow jobs show *Premise —* on the Work orders list (`DEF-WRK-9622`).

### F.3 · Job types

`work_order_types`: **9 types, 21 sub-types (30 rows)**; `work_order_templates`: **6**, all published, all untyped, all
connection-sequence except *Meter exchange — residential* (sequence 0). Which source uses what: New Connect and the
dispatcher — the five connection templates; move-out, move-in, transfer, reconnect, meter read, the Assets door and the
asset age rule — *Meter exchange — residential* (the only non-sequence template, so the only one they are offered);
failed outcome — a copy of the failed job's template. No job type is used by any template.

### F.4 · Stated absences, still true?

| Stated absence | Where | Still true? |
|---|---|---|
| *"work publishes no read keyed on a move record"* (`VISIT_NOT_READABLE`) | `customers/move_record_reads.py` | **False** — `seams.flow_work_acceptance` exists → `DEF-CUS-9628` |
| *Visit: Not raised* | move-in record | **False** — WO-0047, WO-0054 |
| *Changeover read 0 raised* | transfer record | **False** — WO-0048, WO-0055 |
| `DEF-WRK-4003` *"the reconnect visit has … no control on any screen"* | register (open) | **Half true** — the page has the control, but no demo case has a service row to use it on |
| `OQ-WRK-1723` (which meter a reading posts to) | register, OPEN | **True** — and it is why every meter exchange is refused at Accept |

### F.5 · Not filed, and why

* The order page and the field app show times in the browser's zone (06:00 PM for a 1 PM Central window in a UTC
  headless browser) — a real phone in Texas shows 1 PM; not a defect of the product.
* `POST /service-requests/SR-26-0006/transitions` with a request **number** answers 500 (badly formed uuid); the screen
  always sends the id, so no clerk reaches it — noted, not filed.
* A reconnect job could be raised on a case that is only *scheduled* (DSC-26-0001); `BR-WRK-055` does not say a cut must
  precede it — not filed.
* A New Connect build's state needing the clerk's Activate after its last job is accepted may be the design
  (`BR-MET-110`); it is filed as `DEF-MET-9633` because what the clerk sees (*Waiting on: inspection* over an accepted
  inspection) is wrong either way, and ambiguous is a defect.
* **Reds I did not cause:** none run — this lane ran no suite. `DEF-WRK-4096` has been open since **2026-09-05** and
  re-measures true on `2.503.2`.

### F.6 · Proposed walk checks for round 7 (one per source)

| # | Source | The check (as the clerk / the technician, on PG, at 1440 / 390) |
|---|---|---|
| W1 | `new_connect` | Commit a build with two jobs; R. Patel closes both on the phone; office accepts; the build's header names the next act and *Waiting on* no longer names a finished job |
| W2 | `move_out` | Move-out with a visit; close on the phone; accept; the move-out record shows *1 raised · 1 done* |
| W3 | `move_in` | Same on a move-in; *Visit* reads the job, never *Not raised* |
| W4 | `transfer` | Sale with a changeover read; record reads *1 raised · 1 done* |
| W5 | `reconnect` | On a cut case with a service row: raise from the page; close; accept; the row shows the job and *1 raised* after a reload |
| W6 | `service_request` | Approve a request; the child it raises shows its visit; the request links to it (no `route`) |
| W7 | `meter_read` | Reads → *Send someone out*; close; accept; *Raised by* reads a word, the meter's tab shows it in History |
| W8 | `failed_outcome` | Close a job *Failed* on the phone; accept; the follow-up exists, its *Raised by* is a word, the failed job links to it |
| W9 | `dispatcher` | New work order on a premises; close; accept; the premises tab shows it under *All* |
| W10 | `assets` | Raise from an asset; close; accept; the asset's History shows it |
| W11 | `asset_age_rule` | Run the sweep; the job reads *Raised by: Asset age rule* |
| W12 | `dunning_auto` | Final notice expires unpaid; sweep raises a disconnect job; the disconnect wizard's *Work order* rows raise jobs |
| W13 | `high_usage_alert` | A continuous-flow meter; sweep raises a leak job |
| W14 | `billing_exception` | An unresolved bill-run break; sweep raises a read-verification job |
| W15 | `compliance_calendar` | Whatever door `DEF-WRK-4096`'s fix names — or the token is retired by ruling |
| W16 | `payment_received` | A payment on a cut account raises **nothing** (`BR-PAY-036`); the reconnect is the clerk's |
| W17 | the phone | A job with photo-required tasks is closed on the phone alone (photos taken on the task rows); sync refuses a close with a photo missing |

**Defects filed this lane (15):** `DEF-WRK-9619` (field app photos), `9620` (flow meter exchange unacceptable), `9621`
(raw *Raised by* keys), `9622` (*Premise —*), `9623` (service-request route retired), `9624` (*Accepted* / *Not accepted
yet*), `9625` (server close without photos), `9626` (demo offers only meter exchange), `9627` (demo jobs have no source);
`DEF-CUS-9628` (move records' visit), `9629` (transfer changeover count), `9630` (reconnect page), `9631` (disconnect
wizard visits never sent), `9632` (move-in deposit `0.0000`); `DEF-MET-9633` (build state after last accept). Re-measured
open: `DEF-WRK-4096`. **Version:** none — measurement only. **Rollback:** none needed.

## 19 · Round 4 — lane CREWS: three lists, three add forms, one technician's four tabs (`2.505.0`)

**Built from the IMAGES** `05-prototype/work-backoffice-2026-10-04/images/25–34`, on SRV-3's server (`2.502.0`), against
§7.3 and REAL recordings — the reads this lane needed were recorded, not typed: `cr168_capture_work_shapes.py` gained
`--only <prefix,…>` (records only the named reads and MERGES the manifest, so another lane's 49 recordings are not
rewritten from a different database) and eight reads: a technician's jobs (all, open, done), performance (this month,
all time), the add-member picker (`GET /work/technicians`) and the two catalogues (`work_skills`,
`certification_types`). Judgments: decision log *"CR-168 ROUND 4 · CREWS"*. Photographs and side-by-side notes:
`08-qa/work-2026-10-04/after/a25…a34` and `CREWS-side-by-side.md`.

| Task | What a user gets | Where |
|---|---|---|
| P3.49 · ruling 30 | Crews is three lists — Technicians · Crews · Contractors — each its own server page and search, the list in the address, three badges over the whole utility | `CrewsPage.tsx` |
| P3.43 · ruling 26 | *+ Add crew member*: a person from the utility's logins (role · status beside each), Crew, Job title, Shift, Van, EFFECT | `AddCrewMemberModal.tsx` |
| P3.27 · ruling 31 | *+ Add a crew*: Name, Does, Members (anyone on another crew moves), Skills, Shift, EFFECT naming who leaves which crew | `AddCrewModal.tsx` |
| ruling 31 | *+ Add a contractor*: Name, Skills, Hours (by arrangement / set), Phone, Email, EFFECT; no people (ruling 36) | `AddContractorModal.tsx` |
| P3.45 · ruling 27 | a technician's **Jobs**: search, All · Open · Done, Order · Type · Address · Status · Due · Outcome, a moved job says so | `TechnicianJobsTab.tsx` |
| P3.48 · ruling 28 | **Certifications** as a table with *+ Add certification* and Renew; *Valid* / *Expires in N days* / *Expired* (warning only) | `TechnicianCertificationsTab.tsx` |
| ruling 27 | **Performance** (period, four tiles, by job type, paged) and *This month* on the Overview | `TechnicianPerformanceTab.tsx` |
| — | the meta line names the crew and the open jobs (*Field crew A · 2 open jobs*) | `TechnicianDetailPage.tsx` |

**Proved on PostgreSQL 16 at 1440** (`sbh_wcrews`, `10-scripts/cr168_crews_after_walk.mjs`, every write read back through
the API, no response ≥ 400): Sam Reyes added to Field crew B; *Field crew C* added with J. Okoro moved onto it and Water I +
Excavation; *Hill Country Excavation* added by arrangement with its phone and email; D. Ortiz gained *Backflow tester ·
5-yr* to 2031-05-01 and his First aid renewed to 2029-10-22; J. Okoro's First aid (run out 09/22) shows *Expired* as a
warning. **Red first:** `crewsLane.dom.test.tsx` 14 of 14 red on the one-table screen (*no recording for GET /work/crews
without a view*, *expected [Overview, Certifications] to equal [Overview, Jobs, …]*, *expected 'Certification watch…' not
to match /blocked/i*); green after. `CrewsPage.test.tsx` and two `TechnicianDetailPage.test.tsx` cases asserted the
superseded rulings (one table; Jobs absent) and were rewritten, each saying which ruling moved it.

**Server needs, reported to the coordinator rather than built here (SRV-3's files):** a crew row's member NAMES (image 27
draws *D. Ortiz · R. Patel · 2 people*; only the count is served); a job row's completion time for image 32's CLOSED
column; a certificate's document for image 33's PROOF column; the crew of each login on the add-member picker (image 26's
*on Field crew A*); one write that creates a crew with its skills and members atomically; and `GET /work/crews?q=` cuts the
three badges by the search term too (Technicians 5, Crews 0 while searching *Sam*), where the badges should count the
utility. **→ All six served by lane SRV-4 in `2.513.0` (§20.3); the screens draw member names, the picker's crew and the
PROOF column since lane CREWS-2, `2.516.0` (§22).**

**Defects:** `DEF-WRK-9634` (the watch's *blocked* sentence, superseded by PO answer 2) — filed, red, fixed here. **Not
built, by ruling:** a contractor's phone-only logins (ruling 36, field-app document). **Rollback:** redeploy `2.504.0`;
screens only, no migration.


## 19 · Round 4 — lane TEMPLATES: the template list, one template and the builder (`2.506.0`)

Built from images 43–55 (looked at as images, B14 rule 42) on SRV-3's template server (`2.504.0`, `84f08f70d`). Judgments: decision log
*"CR-168 ROUND 4 · TEMPLATES"*.

| Task | What a user gets | Where |
|---|---|---|
| P3.12 · `DEF-WRK-9577` | step 1 asks *Done to* (Premises · Unit · Asset), required; the header sends `scope`; the list has a *Done to* column | `TemplateBuilder.tsx`, `TemplatesPage.tsx`, `templateBuilderModel.ts` |
| P3.13 + PO answer 3 · `DEF-WRK-9565`, `9566` | every added row in Safety, Tasks, Materials, Readings and Help edits in place (a material's unit stays with its part); each task has an instruction line | `TemplateBuilder.tsx` |
| P3.15 · `DEF-WRK-9568` | Review asks *What changed* when a version already stands; Publish sends it | `TemplateBuilder.tsx` |
| P3.25 + P3.14 (screen) · `DEF-WRK-9567` | Help kinds Document · Phone · Link; https only; a video badged; *Choose a file* / *Replace* through the two-call upload; the phone opens a link | `TemplateBuilder.tsx`, `mobile/JobPage.tsx` |
| P3.26 | ONE `TemplateSummary` on Review (step 8) and Overview (image 44) — every row, ✎ Edit to its step | `TemplateSummary.tsx` |
| P3.28 (screen) | the Audit tab reads `GET …/audit`; the *"opens with the next release"* sentence is deleted | `TemplateDetailPage.tsx` |
| P3.29 | *1 order raised across 2 versions* — two plural keys | `TemplateDetailPage.tsx` |
| `DEF-WRK-9582` (builder half) | job type is RAISE's two-level picker | `TemplateBuilder.tsx` |

**Proof.** vitest `cr168Templates.dom.test.tsx` — 15 cases **red on `098dda0a1`** (the tip this lane started from;
output kept in the lane's report), all green after, on SRV-3's RECORDED template (an instruction and a link row),
audit and checklist (`__fixtures__/server/`, never typed); the P3.28 case is red on the old page (*"opens with the next
release"*) and green on the new; one upload case added (its two write answers are SRV-3's stated shapes, walked
against the real server on PostgreSQL). `templateBuilderModel.test.ts` 14 green (the retired *26 items* case is
named in place); `mobile/JobPage.dom.test.tsx` link case red then green; `recordedServerShapes.typecheck.ts` now
checks `work.template.audit.json` against the screen's `TemplateAudit`; tsc clean; `routeBUtilities` shown red on a
planted bad class in `TemplateSummary.tsx`, then green.
**Rollback:** redeploy `2.505.0`; no migration.

### 19.1 · The walk on PostgreSQL (`2.506.1`)

`10-scripts/cr168_templates_after_walk.mjs` on `sbh_wtpl` (migrate + seed_demo + load_sample_data), Dana, 1440:
**35 of 35 checks.** *Meter exchange — single phase* built through all eight steps — Done to *Asset*, an
instruction under *Fit the new meter*, a held PDF, a phone and a YouTube link (an `http` one refused) — with a
row of every kind corrected in place; published v1; ✎ Edit on Overview opened Tasks; a second instruction and
*What changed* gave v2; a job raised afterwards (WO-0043, asset E-5015) carries `template_version` 2 and its
Checklist shows both instructions as second lines. Usage reads *1 order raised across 2 versions*; Audit reads
the trail in words (`GET …/audit` 200). Photographs and notes: `08-qa/work-2026-10-04/after/43…55`, `50c`, `55b`,
`TEMPLATES-side-by-side.md`. **Found on the walk and fixed:** `DEF-WRK-9637` (filed first; red test
`orderPage/orderChecklistHelp.dom.test.tsx` then green) — the checklist printed a held document's id; the
screen never draws an id-shaped `ref`, and **the server half is open**: the job's checklist help rows carry no
file name or url, so the office names the document by its label only. Also fixed: builder boxes ignoring their
widths, *Est.* wrapping. **Rollback:** redeploy `2.506.0`.


### 19.2 · The 16 same-spelled words — lane WORDS (`2.506.3`)

Lane CREWS (`6990bb6da`, `2.505.0`) took `G15`'s fresh untranslated count from **791** (`73517a1d8`) to **807** with the
sixteen values below, each byte-identical to English. Each is judged by the PO's test of 2026-10-04 (decision log
*"A WORD SPELLED THE SAME AS ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER ACTUALLY SAYS"*): would a native
speaker using a utility's back-office software say this word here? **Kept** = added to `G15`'s per-language list
with a one-line reason; **replaced** = written in the spoken word through `10-scripts/i18n_fanin.py`, matching the
term the same catalogue already uses for the same thing. All lines are `NATIVE-REVIEW-OWED` (B14 rule 35).

| Key | Language | Old | New / kept | Why |
|---|---|---|---|---|
| `work.crews.member.person` | de | Person | kept | *die Person* is the ordinary German noun; the counter list already says it |
| `work.technician.performance.minutes` | es | {{value}} min | kept | *min* is the Spanish abbreviation; the catalogue's bill-run tile already prints `{{count}} min` |
| `work.technician.performance.minutes` | es-MX | {{value}} min | kept | as es |
| `work.technician.performance.minutes` | fr-FR | {{value}} min | kept | *min* is the French abbreviation (bill-run tile, same) |
| `work.technician.performance.minutes` | it-IT | {{value}} min | kept | *min* is the Italian abbreviation (bill-run tile, same) |
| `work.technician.performance.minutes` | pt-BR | {{value}} min | kept | *min* is the Portuguese abbreviation (bill-run tile, same) |
| `work.crews.status.active` | fr-FR | Active | kept | the feminine of *actif*, agreeing with *une équipe*; the catalogue already agrees by gender (*une clé* "Active", a person "Actif") |
| `work.crews.status.inactive` | fr-FR | Inactive | kept | the feminine of *inactif*, as above |
| `work.crews.col.certifications` | fr-FR | Certifications | kept | *une certification* is French and the catalogue's own word (*Suivi des certifications*) |
| `work.technician.certifications.title` | fr-FR | Certifications | kept | as above |
| `work.technician.tab.certifications` | fr-FR | Certifications | kept | as above |
| `work.technician.certifications.col.certification` | fr-FR | Certification | kept | as above (*Ajouter une certification*) |
| `work.technician.tab.performance` | fr-FR | Performance | kept | *la performance* is French; the Work module's Performance page and tab already use it — one word, not two |
| `work.technician.jobs.col.order` | id-ID | Order | **Perintah** | English carried over; an Indonesian clerk says *perintah (kerja)*, and the Orders list's same column already reads *Perintah* |
| `work.crews.contractor.email` | it-IT | Email | **E-mail** | the catalogue writes *E-mail* in 21 places (users, customers, notifications); one product, one spelling |
| `work.technician.performance.closedIn` | it-IT | In {{period}} | **Periodo: {{period}}** | *In* before *Da sempre* or *2026* is not Italian (*nel 2026*); *Periodo* is the period picker's own word one line up |

**Count.** 13 kept, 3 replaced. Because `G15` exempts by VALUE within a language, the same judgment also cleared four
values already in the 791 that carry the identical word in the identical language: de `payments.counter.list.col.person`
(*Person*), fr-FR `integrations.keys.state.active` (*Active*, *une clé*), fr-FR `work.performance.title` and
`work.tabs.performance` (*Performance*). So on CREWS' own commit the count would read **807 → 787**. On the tip this
lane started from (`8be67cb16`) it read **839** — 33 newer values are lane TEMPLATES' builder keys (`2.506.x`:
`work.builder.help.sizeKb`/`sizeMb`/`row.cell`/`help.kind.link`, fr `work.template.versionsCount_*`), not judged here —
and after this lane it reads **819**. `g15_untranslated_baseline.txt` is untouched (round 6, `DEF-GOV-9597`).

**Found while reading in context, filed, not fixed:** `DEF-WRK-9640` — with the period set to *All time* the Closed
tile captions *"In All time"* in English (and *"En Depuis le début"* in French, and so on); the Italian line above no
longer has the fault, the other ten do. **Rollback:** redeploy `2.506.2`; no data moves.

## §F.7 · Round 5 — lane FLOW-FIX: the clerk sees the job on the record that raised it (`2.508.0`)

**The PO's question:** *"when work orders are completed is clerk able to see the status update in those requests"*. §F
measured *mostly not*. Every fix below was filed by FLOW-MEASURE; each was proved red first
(`06-backend/tests/test_cr168_flowfix_flows.py`, 12 cases; `tests/test_w6_w7_seed.py` 2 cases; four front-end files).

| Defect | Before (`2.503.2`) | After (`2.508.0`) |
|---|---|---|
| `DEF-CUS-9628` | Move-in *Visit: Not raised* over an accepted job; move-out no visit line | Both records read *1 raised · 1 done · 1 accepted* and link `WO-nnnn`; *Not raised* only when Work says none was (`no_visit_raised`) |
| `DEF-CUS-9629` | Transfer *0 raised · 0 done* (counted by the row's uuid) | Counted by `TRF-` number, the key the job carries |
| `DEF-CUS-9630` | Reconnect rows `work_order: None`; the row's raise posted the service code as a template id and raised nothing | Each row carries its job (number, holder, done/accepted) on every load; the raise posts `{service}` and the server picks the utility's reconnect template |
| `DEF-CUS-9632` | Deposit *Taken 0.0000* | Required, Taken and Still to collect through `MoneyCell` (2 dp) |
| `DEF-MET-9633` | Build *Waiting on: inspection* with every job accepted | The acceptance that leaves no job open clears *Waiting on*, audited; *Approve* stays the clerk's |
| `DEF-WRK-9621` | *Raised by* `work.orders.source.meter_read` / `failed_outcome` | *Meter read* / *Failed job* in all eleven catalogues; a test reads `WORK_ORDER_SOURCES` against every catalogue |
| `DEF-WRK-9622` | *Premise —* on account-anchored jobs | The walk goes account → unit → premises (and asset → point → unit) in one place, `selectors._premises_row`, which the map uses too |
| `DEF-WRK-9624` | *Accepted* beside *Not accepted yet*; failed job did not link its follow-up | The technician's acceptance leaves the line once the job is closed; *Follow-up* / *Follows* link both ways |
| `DEF-WRK-9626` | Every flow offered only *Meter exchange — residential* | Flows offered the templates of their job type (decision log, judgment 1); demo seeds five typed visit templates |
| `DEF-WRK-9627` | 40 of 40 demo jobs *Raised by —* | Build jobs `new_connect` + the build's number; the stand-alone job `dispatcher` |
| `DEF-WRK-9638` | *WO-0043 · unspecified* | Stored name = typed, else job type, else template, never a placeholder; legacy `unspecified` rows read their template's name |
| `DEF-WRK-9639` | Expired certificate badged *cert expiring* | *cert expired* in the danger tier; *expiring* only inside 30 days |

**`DEF-WRK-9623` — a ruling, not a missing door** (decision log 2026-10-04): `route` was retired by the PO on 2026-09-19;
the approved request's child flow carries the visit. `BR-WRK-055`'s first flow needs amending; left open for that.

**Reds I did not cause, dated:** seven, each red on `ef2ceec52` (the tip this lane started from) with the same message —
`test_us_wrk_039_from_flows` tc4 (*closed on acceptance 3 of 3*), tc9 (*16 == 14*: the vocabulary grew to sixteen),
`def_wrk_3725` (*substring not found*); `test_us_wrk_004` (*the only prioritised job leads*); `test_us_wrk_024_027`
tc3, tc7, `026_tc4` (priorities `None`).

**Rollback:** redeploy `2.507.0`. The five seeded visit templates stay on the demo (removable with the sample data);
any `waiting_on` cleared is in `audit_log` with its old value.

## §F.8 · Round 5 — lane FIELD-FIX: the field close, then the technician API (`2.506.2` · `2.509.0`)

**What the PO asked, in order, the same day** (all recorded in the decision log, newest first at the top of the table): finish a job in the field app and let the office accept it; then *"you should create apis for techncian app and use those apis wth payload to complete the jobs"*; one tablet shared by several technicians, offline, with an accurate location; the two consequences ruled (a) and (a); photos 70–100 KB and the 1,000-record proof; *never reject a photo*; records paged both ways with photo links created with the record; Accept held while required photos upload (a); and the sync design delegated to us with one hard rule — *"we cant drop data record in sync process both ways"*.

### F.8.1 · `2.506.2` — the field close (pushed `11b81b9d3`)

| Defect | Was | Now |
|---|---|---|
| `DEF-WRK-9619` | a photo taken in the field app belonged to no task; *2 photographs still needed* never moved | each photo-required task row has its own camera that sends `task_id` |
| `DEF-WRK-9636` (filed this lane) | the job page drew safety rows and tasks as bare boxes; nothing could tick them | tick boxes, through the handset's own sync queue (the office's tick routes answer a field login 403) |
| `DEF-WRK-9625` | the server closed a job with required photos missing when the close came by sync | `submit_field_result` asks `close_readiness` after the cancelled and safety checks — every door |
| `DEF-WRK-9620` | a per-meter job from move-out / move-in / transfer / reconnect carried no meter; Accept said *This job names no meter* | it stands on the unit's meter when the unit's point for the template's service has exactly one; two or more add nothing (not guessed; `OQ-WRK-1723`'s shape) |

### F.8.2 · `2.509.0` — the technician API

Contract: `04-docs/03-contracts/technician-api.md` (every route, payload, answer and refusal key; 26 examples captured from PostgreSQL). Rules: `BR-WRK-059`–`063` and `BR-WRK-047` as superseded. OpenAPI regenerated. Judgments: decision log *"THE TECHNICIAN API AS BUILT"*.

**The walk** (`10-scripts/technician_api_setup.py` raises the jobs through the product's services; `10-scripts/technician_api_walk.py` completes them through HTTP only; PostgreSQL 16 `sbh_wfield`):

| Job | Source | How it was walked | Ended |
|---|---|---|---|
| WO-0042 | move-out | normal, every page sent twice (`--replay`: 5/5 and 1/1 duplicate, nothing added) | accepted |
| WO-0044 | transfer | normal + replay | accepted |
| WO-0049 | New Connect | normal + replay (14 items) | accepted |
| WO-0045 | reconnect | close with a **300 m** fix | accepted; office saw `precise: false` → *Location not precise* |
| WO-0047 | dispatcher | **shared tablet**: Patel captured offline and signed out; Chen signed in, saw none of Patel's jobs (his feed: WO-0025, WO-0048; Patel's job → 404); the device sent Patel's work under Chen's session | accepted; every receipt and the photo attributed to **r.patel** |
| WO-0043 | move-in | closed on the 4th; **Accept refused** — the meter already had a read that day (`DEF-WRK-9642`, filed, not fixed here) | completed, not accepted |
| WO-0018 / WO-0023 | demo jobs | `--refusals`: every documented refusal captured; WO-0023's Accept answered 409 *3 photos uploading* and 200 after the third landed | WO-0023 accepted |

**The 1,000-record proof** (`10-scripts/technician_api_load.py`, WO-0050, PostgreSQL 16):

```
DOWN  1000 readings in 5 pages · 0.24 MB
UP    page 1: 200 accepted=200 duplicate=0 held=0 acked=200
UP    page 2: 200 accepted=200 duplicate=0 held=0 acked=200
UP    page 3: 200 accepted=200 duplicate=0 held=0 acked=200
UP    page 4: 200 accepted=200 duplicate=0 held=0 acked=200
UP    page 5: 200 accepted=200 duplicate=0 held=0 acked=200
UP    page 6: 200 accepted=200 duplicate=0 held=0 acked=200
UP    page 7: 200 accepted=200 duplicate=0 held=0 acked=200
UP    page 8: 200 accepted=200 duplicate=0 held=0 acked=200
UP    page 9: 200 accepted=200 duplicate=0 held=0 acked=200
UP    page 10: 200 accepted=200 duplicate=0 held=0 acked=200
REPLAY page 1: duplicate=200/200 · same links: True
IMAGES interrupted after 400 · {'landed_or_staged': 400, 'duplicate': 0, 'hash_mismatch': 5, 'resent_after_mismatch': 5}
RESUME: 600 links still pending (expected 600)
IMAGES done · {'landed_or_staged': 1000, 'duplicate': 10, 'hash_mismatch': 5, 'resent_after_mismatch': 5}
RECONCILIATION (server): {"technician": {"name": "R. Patel"}, "items_stored": 2066, "items_held_for_review": 1, "by_kind": {"close": 7, "material": 5, "photo": 1011, "reading": 1008, "safety_tick": 12, "task_tick": 23}, "photos_declared": 1011, "photos_landed": 1011, "br_ref": "BR-WRK-063"}
TIMINGS (wall clock):
   1 down: 1,000 readings, paged                                      0.2 s
   2 up: 2,000 records in 10 pages (no image)                        34.9 s
   3 replay: page 1 again                                             0.9 s
   4a images: first 400, then the connection drops                   61.0 s
   4b images: resume the remaining 600 (+10 deliberate re-sends)    157.5 s
   6 close + accept                                                   0.6 s
MOVED: down 0.24 MB · up (records) 1.77 MB · images 135.50 MB
ACCEPT: 200 
```

Database after the run: 2,001 receipts (2,000 items + the close), 1,000 links all landed, 1,000 attachments with 1,000 distinct keys, largest stored photo 102,355 bytes, 50 photos received over 100 KB and shrunk, 0 links still holding staged bytes. **Zero dropped, zero duplicated.** No request came near the 60-second worker limit (the slowest page of 200 items took about 3.5 s), so no performance defect is filed.

**Reds I did not cause** (each re-run on the tip `abda50e48` before my change and red there too): `test_w6_the_gate_flag_is_stamped_from_its_template` (`template_not_published`), `test_w9_transfer__task_5` (`set_target_unit`), `test_us_wrk_039` tc4 / tc9 / 3725, `test_us_wrk_002_a_build_with_no_common_area` (`identity_kind_required`), `test_us_wrk_005_tc6[metering_seam]` (the seam publishes `create_template` and four more write verbs).

### F.8.2b · The field app itself, walked in a browser (`10-scripts/cr168_field_fix_walk.mjs`, `2.509.0`)

R. Patel at **390 × 844**, nothing sent beforehand by any API: WO-0051 (raised from a **move-in**, standing on meter E-5007 — `DEF-WRK-9620`) — ticked the safety line and both tasks on the job page (`DEF-WRK-9636`), took the photograph on the task's own *Photo* control (`DEF-WRK-9619`: *Photo taken.*, the close pane then listed **nothing still needed** and *Close job* was enabled), read 4,120 kWh, closed *Passed*. Dana at **1440**: the order read *Awaiting approval · … · Location not precise* (the web field app sends no location fix — truthful), Accept → *Accepted*; the meter's history holds 4,120 kWh dated 4 Oct. Photographs `08-qa/work-2026-10-04/flows/fixed/01`–`09`, every one opened.

### F.8.3 · Left, said plainly

* **Office notifications** on close, on photos complete and on *Needs review*: not built. The notifications module has no staff-addressed message kind to queue them under; adding one is that module's work.
* **A cross-tenant PostgreSQL probe on `work_photo_links`** (the RLS policy is applied and reversible; the probe is owed).
* **The field app's own screens** do not yet use the capture token, the photo link or the change feed — they still sync with the session (that path is unchanged and still works). The API is the contract; moving the screens onto it is the next step.
* **Device-side "captured" count** for the reconciliation: the server states its side; the phone's `itemsWaiting` is the other half, compared on the device.
* **`DEF-WRK-9642`** (Accept refused when the meter already has a read that day) is filed for the office's Accept, not fixed.

### §F.7.1 · The walk on PostgreSQL (`2.509.2`)

`10-scripts/cr168_flowfix_walk.py` on `sbh_wflowfix` (migrate + `seed_demo` + `load_sample_data`), backend `2.508.0`
(this push's front-end changes built on top) on :8065, the bundle on :5195. Every job raised through the flow's own HTTP door as Dana, assigned to
**R. Patel**, closed by him through `POST /work/mobile/jobs/{id}/sync` (signed in on the mobile surface, required
photographs taken FOR their rows), accepted by Dana; every record then read back from the server and photographed at
1440 (`08-qa/work-2026-10-04/flows/fixed/`, `fx01`–`fx11`, each opened).

| W | Source | Raised | After acceptance, on the record the clerk opens |
|---|---|---|---|
| W2 | move-out `MVO-26-0002` | `WO-0042` *Final read* | *Visit 1 raised · 1 done · 1 accepted WO-0042* (`fx01-…-raised` showed *1 raised · 0 done · 0 accepted*) |
| W3 | move-in `MVI-26-0004` | `WO-0043` *Opening read* | same; *Taken $0.00* (was `0.0000`) (`fx02`) |
| W4 | transfer `TRF-26-0001` | `WO-0044` *Changeover read* | *Changeover read 1 raised · 1 done* (`fx03`) |
| W5 | reconnect `DSC-26-0001` | cut (water), then the row's raise → `WO-0046` *Reconnect visit* | reload: *WO-0046 · R. Patel · Accepted*, *1 raised · 0 to raise* (`fx04`) |
| W1 | New Connect `CON-26-0126` | its last 2 jobs | *Waiting on: inspection* gone; *Approve* in the head (`fx05` before/after) |
| W1 | New Connect `CON-26-0124` | its 5 jobs | *5 of 5*; stays *Requested* with *Approve* — activation is the clerk's (`CR-162-BRC10`) (`fx06`) |
| W7 | meter read `W-5049` | `WO-0047` *Re-read* | *Raised by Meter read* (`fx08`) |
| W8 | failed outcome | `WO-0048` failed → `WO-0049` | *Follow-up WO-0049* / *Follows WO-0048*, *Raised by Failed job*, no *Not accepted yet* (`fx09`, `fx10`) |
| — | Orders list | `WO-0045` (reconnect, account-anchored) | *Premise 77 Industrial Way*, *Raised by Reconnect* (`fx07`) |
| — | Crews | J. Okoro | *cert expired*, danger tier; D. Ortiz *cert expiring* (`fx11`) |

**Found on the walk, filed, not fixed:** `DEF-WRK-9645` (a move-in's template offer is empty once the outgoing account
is closed), `DEF-CUS-9646` (transfer commit 500 on an unknown buyer kind), `DEF-WRK-9647` (a failed job's follow-up
carries no service — `fx10` *Service —*), `DEF-CUS-9648` (a malformed account id on the cut route answers 500). The
walk itself raised one reconnect job twice before its resume was written (`WO-0045` open); left as data. **The demo's
four disconnect cases are all before the cut with no service chosen**, so the reconnect page has no row until a clerk
schedules services and records the cut — the walk did both through the product. ⚠ **Twice in this push a sibling took the defect numbers this lane had allocated
before it pushed** (`9642`, then `9643`); each time the rows were withdrawn and re-filed from the new tip (law 11).

## §F.9 · Round 5 — lane FIELD-2: the field app on the technician API, and the office told (`2.509.1` · `2.510.0`)

What FIELD-FIX left (§F.8.3), built. Judgments: decision log *"THE FIELD APP ON THE TECHNICIAN API, AND THE OFFICE TOLD"*.

| Item | Now |
|---|---|
| The field app's screens | Every tick, reading, photograph and close goes through one door (`mobile/capture.ts`): stamped AT CAPTURE with the signed-in technician's capture token and the job's best location fix, written to the phone, then sent. The outbox is sent in pages of at most 200 and an item leaves the phone only on ITS acknowledgement. Photographs: the data (photo id, sha256, task or reading) travels in the page and the server makes the link; the bytes stay on the phone and upload to that link in the background, and are let go only when the server has them. Bundles refresh from the change feed with a cursor per technician; the day and bundles are kept per login, so the next technician on a shared tablet sees none of the last one's jobs. Location starts when the job opens and keeps the best fix. *N waiting to send* is always on screen. A job not yet taken shows **Accept job** (an item captured before acceptance would be held for review). Sign-out sits in the bottom bar, never blocks and never deletes. |
| Office notifications | New notifications kind `field_work`, template `staff_field_work` (in-app). *Closed* (with the photos still uploading), *photos in · ready to accept*, *N field items need review* — in the clerk's own language in all eleven catalogues. To whoever sent the job to the field; Needs review also to every System Admin (BR-NOT-021 unchanged). |
| Cross-tenant probe on `work_photo_links` | `tests/test_cr168_photo_links_rls_pg.py`, on PostgreSQL 16 under the probe role: ENABLE + FORCE, nothing without a tenant, Brazos Bend's link invisible to Lone Star by row and by the phone's own photo id, and a write stamped for another tenant refused by the policy. |
| `DEF-WRK-9643` | An accepted order reads *Completed · Passed · Accepted* (`2.509.1`). |

**The walk** (`10-scripts/cr168_field2_walk.mjs`, PostgreSQL 16 `sbh_wfield2`, jobs raised by `technician_api_setup.py` as Dana; photographs in `08-qa/work-2026-10-04/flows/field2/`, every one opened): R. Patel at 390 × 844 opens WO-0041 and takes it online (02); the signal goes (Playwright offline); he ticks safety and both tasks, photographs the meter on its task row (03, *4 waiting to send*), reads 4,120 kWh (04), closes *Passed* with *Location within 8 m* (05) — *1 job to send · 6 waiting to send* (06); signs out with no signal (07). M. Chen signs in on the same tablet: his own WO-0047 only, and *6 waiting to send* — a number, nothing of Patel's (08). The data signal returns: the page goes, the photo is held a little longer (09, *1 waiting to send*). Dana at 1440: *Completed · Passed · Awaiting approval*, **1 photo uploading** and Accept unavailable (10); her bell: *WO-0041 closed · 1 photo uploading* (11). The photo arrives (12, *0 waiting to send*); her bell: *WO-0041 photos in · ready to accept*; Accept is available and the order carries **no** *Location not precise* (13, 14). On the server every one of the six receipts is **r.patel@sample.test** with accuracy 8.0 m, though Chen's session carried them; `close_location.precise = true`. Dana's Accept was then refused by `metering.event_reads.errors_refuse` — the meter already had a read that day: `DEF-WRK-9642`, waiting on the PO, not touched here.

The first run (WO-0046) is kept in the record because it found two things: the app had no way to take a job, so all six items were held *accept the job first* and the office was told *WO-0046: 6 field items need review* (the Needs-review path, end to end) — which is why **Accept job** exists; and the held photograph's bytes had no link to go to (`DEF-WRK-9652`, filed, open).

**Left, said plainly.**
* `DEF-WRK-9652` — a photograph whose data item is held for review has no link, so its bytes stay on the tablet and *waiting to send* never reaches zero. Where held photo bytes should go is the API's design question; nothing is dropped meanwhile.
* A tenant provisioned before `2.510.0` gets `staff_field_work` the next time `seed_notice_templates` runs for it (insert-missing; proved on `sbh_wfield2`). Until then its field messages are queued and hold at dispatch with the missing-template reason.
* The signature and a refused signature's door-hanger photograph are still posted directly (online only), now with the capture token.
* Accept job is an online act; offline the button is shown and fails with *Could not accept. Try again.*

## 20 · Round 5 — lane SRV-4: the rules server and the promise (`2.512.0` …)

Server only; the screens are lanes RULES and PERFORMANCE's. Judgments: decision log *"CR-168 ROUND 5 · SRV-4"*. Built
from §7.3, images 56–65 (looked at as images) and the blueprint's ruling-10 table of processes.

### 20.1 · `2.512.0` — every rule raises, under its own label

| Task / defect | What a user gets | Where |
|---|---|---|
| `DEF-WRK-4096` · P3.31 | A rule's job reads its PROCESS's label — `dunning_auto`, `billing_exception`, `asset_age_rule`, `high_usage_alert`, `compliance_calendar`, `meter_read` — the order table's own vocabulary. Wave M stamped the module name and the table refused four of five | `work/rule_processes.py`, `work/rules.py` |
| `DEF-WRK-4097` · P3.33 | Continuous flow REQUIRES a service and a unit; the minimum is compared only with readings in its unit (a reading in another unit breaks the run); the last N readings per meter are cut in SQL (`ROW_NUMBER() OVER …`). Demo: 98 subjects → 47 (water, kgal) | `work/seams/metering_seam.py` |
| P3.30 | `GET /work/rules/processes` — **twelve** processes `{key, label, module, source_label, moment: overnight\|screen\|retry, params[]}`, the read-only estimate limit, and the Notify step's vocabularies (`assign_kinds`, `escalation_kinds`, `notify_when`, `notify_who`, `also_tell_kinds`) | `work/rules.py` |
| P3.32 | Two new overnight readers: *certification due soon* (`days_ahead`, required; subject = asset@due date) and *a meter at its estimate limit* (Meter-read settings' `est_max_consecutive`, never copied; subject = meter@run end) | `work/seams/assets_seam.py`, `metering_seam.py` |
| P3.34 | A rule on a screen moment (move-in, move-out, transfer, reconnect, new connection) is read by `from_flows.propose` → each offered row gains `preselected_by {id, name}` (a rule's template outside the offer is added, ticked); `raise_for` applies the rule's priority, due date and assignee to a ticked job. Nothing raised overnight. The move-in trigger (`occupancy_completed`) is read as this moment | `work/from_flows.py`, `rules.preselection`, `rules.shape_by_rule` |
| P3.35 | A rule on *a job is accepted as failed* naming the failed job's template sets the retry's priority and assignee — never a second job (metering resolves `rules.shape_by_rule` by name, in its own savepoint) | `metering/connections.py` `_shape_retry_by_rule` |
| P3.36 | *Give the job to* is READ at the raise: `technician`/`crew` (named), `skill` (the matcher's best fit, advice), `area` (best candidate already working in the job's area that day), `nobody` | `rules.assign_by_rule` |
| P3.38 | One subject, one open job per template, whoever raised the first: the sweep counts `already_open`; a screen's raise answers `already_open[] {template_id, order_no}` | `metering_seam.open_order_for_template` |
| P3.61 | `last_fired_at` and `jobs_raised` beside `this_month`, from the memory, annotated in ONE query on the list | `rules.rules_page` |
| P3.65 | `triggers[] {kind, params}` (≥ 1, any raises; two triggers on one meter raise ONE job) written to `work_order_rule_triggers`; wave M's columns kept, filled from the first | `rules._clean_rule`, `_write_triggers`, `subjects_tonight` |
| §7.3 rules writes | `assign_to`, `notifications[] {event_key, when?, who?}` (catalogue keys only), `escalations[] {kind ∈ seven, after_hours, also_tell[] {kind: role\|user, id}, event_key?}` (stored; fired by the next push), `reminders` refused; `incomplete[]` names a trigger missing a required setting | `rules._clean_rule` |
| reads | `GET /work/rules/{id}` adds `tonight {subjects, would_raise, already_open}` (read-only); `POST /work/rules/preview`; `GET /work/rules/{id}/jobs` and `…/audit`, paged in SQL; `GET /work/rules?q=` searches name, template and process words | `work/api.py` |
| `DEF-WRK-9645` | A move-in asked about a closed outgoing account is offered the unit's services' templates | `from_flows._resolve_move`, `metering_seam.service_codes_on_unit` |
| `DEF-WRK-9647` | A failed job's follow-up carries the failed job's service (the chain sent `service_id`, a key nothing reads) | `metering/connections.py` |
| `DEF-WRK-9623` | Not a missing door: `BR-WRK-055` amended to the PO's 2026-09-19 retirement of *route* — four doors, the request reaches field work through its child flow; `from_flows.FLOW_SERVICE_REQUEST` says so | `16-work/02-business-rules.md` |

**Appended to §7.3 by lane SRV-4:** `GET /work/rules/processes` also serves `settings`, `assign_kinds`,
`escalation_kinds`, `notify_when`, `notify_who`, `also_tell_kinds` (the form types no literal); rules rows add
`assign_to`, `incomplete[]`, `tonight` (detail only); `POST /work/rules/preview`; the raise answer of a flow adds
`already_open[]` and each raised row `rule`; refusal keys `work.rules.param_required`, `param_invalid`,
`assign_invalid`, `also_tell_unknown`, `notify_row_invalid` beside the five §7.3 named (eleven catalogues).

**Proof.** Red first on `10c481e34` (output kept in the lane's scratch, quoted): `test_cr168_srv4_rules.py` — dunning
`assert 0 == 1`, billing `assert 0 == 1`, asset age `assert 'assets' == 'asset_age_rule'`, continuous flow `assert 0 ==
1`, the new processes `VAL-005 (work.rules.triggerUnknown)`, the move-in rule `the overnight sweep must not read a
screen moment`; `test_cr168_srv4_flows.py` — `9645` `assert 0 >= 1`, `9647` `assert None is not None`, P3.34/P3.35/P3.38
red. `test_cr168_srv4_rules_pg.py` on PostgreSQL 16 on `10c481e34`: `assert 1 == 4` (one job of a four-process night,
under `assets`). After: **26 passed on PostgreSQL 16**, 24 on SQLite; `US-WRK-037` TC-3 and the M6 PG case asserted
`source == "assets"` — the defect — and now read `asset_age_rule` (the ratified figure, three and none, unchanged).

**Reds I did not cause, dated:** `test_us_wrk_037_rules_pg.py::test_m6…` red on `10c481e34` too (*`assert 1 == 0`*,
Lone Star sees Brazos Bend's rule: the shared server's `postgres` role is a superuser and bypasses RLS — environment);
`test_us_wrk_039` tc4, tc9, `def_wrk_3725`, and `test_us_wrk_024_027` tc3, tc7, `026_tc4` (priority `None`) — the six
FLOW-FIX dated on `ef2ceec52`, same messages.

**Rollback (20.1):** redeploy `2.510.0`; no migration of its own.

### 20.2 · `2.512.0` — the promise (P5)

| Task | What a user gets | Where |
|---|---|---|
| P5.9 · PO answer (1) | *SLA met* counts every completed job with a promise: its own `due_at`, else its raise + the DEFAULT target's hours (Normal, 72 h). Tiles add `sla_measured`/`sla_met` so the headline is its rows' sum (P5.1's server half). Red first: `assert '50.0' == '66.7'` | `work/promise.py`, `selectors.performance` |
| P5.2 · P5.8 | Held time is excluded: the promise moves by `held_seconds` (and the running hold on an open job). The columns are SRV-1's (`metering/0071`); the order list's `sla` already paused — Performance did not. Red first: `assert '0.0' == '100.0'` (two days of rain read as a breach) | `promise.held_expr` |
| P5.6 | `GET /work/performance?period=&page=&per=&sort=&dir=` — ONE annotated set (promise, followed?, cost = sum of ROUNDED lines, `BR-WRK-051`), tiles and rows both aggregates over it, the table `ORDER BY … LIMIT/OFFSET`; `by_job_type` kept one round for the screen on the tip | `selectors.performance`, `api.work_performance` |
| P5.10 | `PATCH /work/job-types/{id} {sla_hours}` — a type's own hours override its priority's at the raise (and a priority change then moves the pill, not the date); blank = the priority's; a promise already stamped never moves | `promise.set_job_type_sla`, `metering.connections._resolve_due_at`, `dispatch.change_priority` |
| P5.3 (read) | `GET /work/at-risk?page=&per=` — open jobs whose promise (+ held time) falls within `work_settings.at_risk_window_hours` (`work/0037`, NULL = only past), soonest first, each with `promise {due_at, target, overdue, minutes_left}`; `GET/POST /work/settings/sla` carry `at_risk_window_hours` | `promise.at_risk_page`, `workforce.set_default_target` |

**Migration `work/0037`** (🔒, `HUMAN-REVIEW-PENDING`, review-ledger row): up → down → up on PostgreSQL 16 (`sbh_wsrv4`),
`makemigrations --check` clean. **Superseded case rewritten:** `US-WRK-054` TC-2 asserted *an undated job is out of
the denominator* (`50.0%`); PO answer (1) makes it `66.7%`, and the case says so. `test_cr168_srv4_promise.py` 6 green
on SQLite and on PostgreSQL 16 (interval arithmetic in the database on both engines).

**Rollback:** redeploy `2.510.0`, then `migrate work 0036`.

### 20.3 · `2.513.0` — escalations fire, reminders live in Notifications, and the Crews server gaps

Judgments: decision log *"CR-168 ROUND 5 · SRV-4 (ESCALATIONS, REMINDERS AND THE CREWS SERVER)"*.

| Task / gap | What a user gets | Where |
|---|---|---|
| P3.57 | A rule's *When it stalls* rows FIRE: an hourly sweep (`work.escalations_sweep`, the `work` queue, one per utility per hour) reads each enabled rule's rows against the jobs that rule raised or shaped — *nobody assigned*, *not accepted*, *running late*, *past due* (held time added back, P5.2), *on hold too long*, *failed*, *awaiting approval* — ONCE per job per kind (`work_order_rule_escalation_fires`, a SAVEPOINT), audited `work.order.escalated` | `work/escalations.py` |
| P3.58 | Six catalogue rows — `work_job_not_assigned`, `work_job_not_accepted`, `work_job_running_late`, `work_hold_overdue`, `work_job_failed`, `work_approval_overdue` — and `sla_breach` (*past due*) gains its writer; in-app, FIELD-2's `staff_field_work` class, each with the utility's own switch. Told: whoever sent the job out + every System Admin (`BR-NOT-021`) + the row's *Also tell* (PO 2026-10-04) | `notifications/rule_catalog.py`, `notifications/work_escalations.py` |
| P3.59 | Two reminders join Notifications: `certificate_expiring` (30 days, the certification watch's window; every System Admin, once per certificate per expiry date) and `technician_day` (the technician, once a day, jobs held today). A rule carrying `reminders` is still refused | same, `work/escalations.remind` |
| CREWS gap 1 (image 27) | A crew row carries `member_names` (*D. Ortiz · R. Patel*) beside the counted `members` | `workforce._crew_list_row` |
| CREWS gap 2 (image 32) | Every dispatcher row carries `completed_at`; the Jobs tab draws *Closed* on every row — **CREWS' hold expired and its test now asserts the column unconditionally** (it read `served ? 7 : 6`) | `dispatch._dispatch_row`, `TechnicianJobsTab.tsx`, `crewsLane.dom.test.tsx` |
| CREWS gap 3 (image 33) | `POST …/certifications/{type_id}/proof` (PDF/PNG/JPG ≤ 10 MB) and `…/proof/content` (same-origin, `private, no-store`); a certificate row on the technician's page carries `proof {id, name, content_type, bytes, url}` or null; a renewal keeps it (`tenancy/0060`, 🔒) | `work/certificate_proof.py` |
| CREWS gap 4 (image 26) | `GET /work/technicians?q=&page=&per=` paged in SQL (NFR-3), each login with `technician_id` and the `crew` it is on; the picker asks for 200 by name until it searches on the server | `workforce.staff_page`, `identity_seam.staff_users_queryset`, `crewsEndpoints.listStaffChoices` |
| CREWS gap 5 (image 29) | `POST /work/crews` takes `skills[]` and `members[] {technician_id \| user_id}` in ONE transaction; a member on another crew moves and is named in `moved[]`; an unknown member rolls the crew back; a contractor takes no members | `workforce.create_crew` |
| CREWS gap 6 (image 25) | The three badges count the utility while a search is typed; the page's `count` follows the search | `workforce.crews_page` |

**Recorded for lanes RULES and PERFORMANCE** (`cr168_capture_work_shapes.py --only …`, PostgreSQL 16, `sbh_wsrv4`, after one rules sweep and a 72 h warning window on the demo): `work.rules.processes` (12), `work.rule` (with `tonight`), `work.rule.jobs` (3), `work.rule.audit`, `work.performance.paged` (7), `work.at-risk` (20), `work.settings.sla`; re-recorded `work.rules`, `work.performance`, `work.crews.*`, `work.technician*` (D. Ortiz's First aid carries a stored proof) and `work.technicians`. Manifest 58 → 65 reads. The re-recorded `work.rules` showed `notifications` arriving as a LIST since `2.512.0` while `WorkRuleRow` typed an object — `tsc` caught it; the type now says list (nothing on screen read it).

**Defect:** `DEF-TEN-9655` — a stored-document migration's rollback refusal ran LAST on the way back (Django reverses operations) so the narrower CHECK refused first with a raw IntegrityError; measured on `0060` with a live proof, fixed in `0060` (refusal moved to the end, counted sentence quoted in the review-ledger row). **Left open** for the same order in tenancy `0020`, `0028`, `0039`, `0040`, `0044`, `0045`, `0051`, `0052`, `0054`, `0059` and work `0034` — the database still refuses each (atomic DDL), only the sentence is wrong. **→ Fixed by lane CREWS-2 in `2.516.0` (§22)** — ten of them; `0020` carries no refusal.

**Proof.** Red first on `cf7ce09cc` (the new tests copied into a worktree at the tip): 15 of 16 red — `KeyError: 'member_names'`, `{'crews': 0} != {'crews': 1}`, `KeyError: 'completed_at'`, `no attribute 'staff_page'`, `assert 0 == 2`, `DID NOT RAISE`, `cannot import name 'certificate_proof'`, `cannot import name 'escalations'` ×6, `'work_job_not_assigned' in {…}`; the 16th (a rule may not carry reminders) was built in 20.1. CREWS' hold test on the tip's recordings: `expected false to be true`. After: 34 passed on PostgreSQL 16 (`test_cr168_srv4_crews.py`, `test_cr168_srv4_escalations.py`, `test_cr168_srv3_crews.py`) and on SQLite; vitest `src/features/work` + `src/features/notifications` 72 files, 850 passed; `src/i18n` 74 passed; `tsc` clean. Superseded cases rewritten, each naming the change: `test_cr168_srv3_crews` (badges followed the search), `test_cr_009` (32 → 40 events, 12 → 11 blocked; `sla_breach` live), `test_cr048_a1` (the no-template example moved to `daily_digest`).

**Reds I did not cause, dated on `cf7ce09cc`:** `test_cr048_a1…switched_off_channel_leaves_no_row_at_all` (`{'pdf_print', 'portal'} == {'pdf_print'}`), `test_oq1164…seventeen_kinds…` (`'in_app' in FREEZE_CHANNELS`) and `test_oq1164…each_of_the_twelve…[staff_field_work]` (`KeyError: 'staff_field_work'`) — red on the tip with the same messages. A wider regression run (every `test_us_wrk_*`, `test_cr168_*` and the notification-catalogue suites, 919 cases on SQLite) ended 781 passed, 24 failed, 10 errors; **all 34 are red on `cf7ce09cc` too** (re-run there by name, same set) — among them the six FLOW-FIX dated, `test_cr048_b_engine_on` b8/b9 and `test_cr048_b6_b10` (counts and adapters that predate this lane), `test_br_cus_094a` (`NOT NULL … accounts.account_type_id`) and `test_us_ten_002`. G98 (lint) is red on `TemplateDetailPage.tsx` (`Fact`, `FactList` unused, since `83af69670`, lane TEMPLATES). `run_gates --changed`: 0 newly failing.

**Rollback (20.3):** redeploy `2.512.0`, then `migrate tenancy 0059` — refused with a count once any proof is stored; stay on `0060` then (the rows are write-once).

## 21 · Round 5 — lane PERFORMANCE: the headline adds up, and the three boards P5 names (`2.514.0`)

Judgments: decision log *"CR-168 ROUND 5 · PERFORMANCE"* (seven, none put to the PO as a question).

| Task | What a user gets | Where |
|---|---|---|
| P5.1 · `DEF-WRK-9586` | The *SLA met* tile reads *24 of 24 kept* and *Undated: 72 h promise* (from `GET /work/settings/sla`) under the figure — the tile is the rows' sum and says so | `PerformancePage.tsx` (`PerformanceResults`) |
| P5.6 (screen half) · `DEF-WRK-9656` | The table sends `page`, `per`, `sort`, `dir` and reads `results`/`count`; five columns sort on the server; `by_job_type` removed from the API | `PerformancePage.tsx`, `workEndpoints.fetchPerformance`, `apps/work/api.py` |
| P5.3 | *At risk*: open jobs near or past their promise, soonest first, *Late 1 d 6 h* (danger) / *2 h 56 m left* (warning), the window and count in one fact line | `performance/AtRiskBoard.tsx` |
| P5.4 | *Schedule*: a day and a window; *Unassigned jobs* (`GET /work-orders?technician=none`, paged) beside *Who can go* (`GET /work/candidates?on=`, paged, each holder's jobs that day and a load pill — *Off, has jobs* in red); drag a job onto a holder, or tick and *Give ✓* — one `POST /work-orders/bulk` assign with the day's window | `performance/ScheduleBoard.tsx` |
| P5.5 | *Raise across buildings*: a template, the asset registry (`f.assigned`, the template's service, *Due for test*), ticks that survive paging, *Raise N jobs ✓* → `POST /work-orders/bulk-raise {asset_ids}` with NO premises, the raise's own per-job result | `performance/RaiseAcrossBoard.tsx` (reuses `RaisePickTable`, `RaiseResult`) |

All three boards are views of the Performance tab (`?view=`), every selection table the kit `TableArray`, every list paged on the server. P5.11 holds: no new endpoint.

⚠ **SUPERSEDED IN PART 2026-10-05 (§30, lane BOARDS).** The PO answered: *"(b) Make At risk its own tab next to Orders … Schedule and Raise across buildings stay inside Performance."* At risk is now `/work/at-risk` (`WRK-25`); `?view=at-risk` forwards there. And the *Left* line below about a capacity figure is answered: a daily job limit, default 6 (§30).

**Recorded shapes:** `work.performance.paged`, `work.at-risk`, `work.settings.sla` added to `recordedServerShapes.typecheck.ts` (`tsc` clean); the screens' tests read them. The asset rows in the across-buildings test are the Assets module's `AssetRow` (no Work recording reads `/assets`), said in the test's header.

**Proof.** Red first on `3cd891cfb`: the new dom file failed to load (`Failed to resolve import "./RaiseAcrossBoard"`); with the board cases cut, the old screen failed `Unable to find … work.performance.tile.slaKept` and `expected undefined to be 1` (no page sent); the server case `assert 'by_job_type' not in {…}`. After: vitest `src/features/work/performance` + `PerformancePage.test.tsx` + `recordedServerShapes.dom.test.tsx` green; `test_cr168_perf_lane.py` (4) + `test_cr168_srv4_promise.py` on SQLite and PostgreSQL 16. Walked on PostgreSQL (`sbh_wperf`, `10-scripts/cr168_perf_walk_prep.py` then `10-scripts/cr168_perf_walk.mjs`, 1440): headline 100.0% = 24/24, rows sum 24/24, volume 24 = 24, `by_job_type` absent; at risk 18 rows in a 72 h window, 3 late; WO-0018 dropped on R. Patel (*Given to R. Patel: 1.*); three assets on two buildings raised WO-0046…0048.

**Photographs** (`08-qa/work-2026-10-04/after/`): `a65-performance.png`, `a65b-at-risk.png`, `a65c-schedule.png`, `a65d-schedule-dropped.png`, `a65e-raise-across-picked.png`, `a65f-raise-across-result.png` — each opened and checked, none blank.

**Side by side with image 65:**

| Image 65 | Built (`a65-performance.png`) |
|---|---|
| Title, eight tabs, Performance underlined | the same |
| Description *How the field did against its promises, and what it cost.* | the same; under it, NEW, the four-view strip (the boards' only door) |
| Four tiles: *SLA met 100.0%*, *First-time fix*, *Cost per job $7.90 Recorded*, *Jobs completed 23* | the same four; *SLA met* gains two fact lines, *24 of 24 kept* and *Undated: 72 h promise* (P5.1) |
| ▦ column chooser top right of the table | the same |
| Six columns, rows by volume | the same; five headers sort on the server (▼ on Volume) |
| *1–7 of 7*, Rows per page 50, ‹ › | the same, and the pager now moves the server page |
| *Total field cost 23 $181.73* | the same, from the server's `total` |
| CHECK box *These figures are recorded here.* | the same |
| Image figures (100.0% over 0.0% rows, 23 jobs) | illustrations (rule 37); the demo reads 24 jobs all kept, so the tile and rows agree at 100% |

**The three boards go to the PO as photographs** (`a65b`, `a65c`/`a65d`, `a65e`/`a65f`) — the decision to make is the layout and the placement (a view of Performance, or a tab of its own), not whether they ship: they ship in `2.514.0`.

**Left:** a jobs-per-day capacity (no such fact is stored; over-assigned is *off that day with jobs*); the schedule board shows a holder's COUNT, not the jobs themselves (no day filter on `GET /work-orders` — `BR-WRK-026` keeps six); P5.7 (`journeys/sla-breach.md`) is not written here.

**Rollback:** redeploy `2.513.0`. No migration.

## 22 · Round 6 — lane CREWS-2: the Crews screens draw what SRV-4 serves, and five defects (`2.513.1` · `2.516.0`)

**Built from the IMAGES** `05-prototype/work-backoffice-2026-10-04/images/26, 27, 33, 34` on lane SRV-4's server (`2.513.0`),
typed against the recorded answers in `07-frontend/src/features/work/__fixtures__/server/` (nothing hand-typed; no re-recording
was needed — `work.crews.crews`, `work.technicians` and `work.technician` already carry `member_names`, `crew` and `proof`).
Judgments: decision log *"CR-168 ROUND 6 · CREWS-2"*.

| Task / defect | What a user gets | Where |
|---|---|---|
| CREWS gap 1 (image 27) | The Crews list's MEMBERS reads *D. Ortiz · R. Patel · 2 people* — the names, then the counted members, muted | `CrewsPage.tsx` |
| CREWS gap 4 (image 26) | *+ Add crew member*'s Person list reads *Field technician · on Field crew A* for a login on a crew, *Executive · Invited* for one on none | `AddCrewMemberModal.tsx` |
| CREWS gap 3 (image 33) | Certifications draws **PROOF**: the scan's name, opening it in a new tab, or a dash. Add / Edit carry an optional **Proof** field (PDF or photo, up to 10 MB; refused on screen otherwise; on Edit it names the scan on file) | `TechnicianCertificationsTab.tsx`, `crewsEndpoints.uploadCertificateProof` |
| `DEF-WRK-9640` | Performance with *All time* captions Jobs closed *To date* (it read *In All time*; ten of eleven languages were wrong) | `TechnicianPerformanceTab.tsx`, `work.technician.performance.closedAllTime` |
| `DEF-WRK-9652` | A photograph whose item is HELD for review still gets its link: the bytes leave the tablet, are filed to the job, and the flag stays on the receipt; a held link never holds Accept | `photo_links.declare_held`, `sync._hold` |
| `DEF-CUS-9646` | A sale's buyer with a type other than person/company is refused by name (422), not 500 | `transfers._validated_buyer` (`2.513.1`) |
| `DEF-CUS-9648` | All nine disconnect-case writes answer 404 for a malformed or absent account (they answered 500 / 422) | `transfer_disconnect_api` (`2.513.1`) |
| `DEF-TEN-9655` | The rollback refusal is the LAST operation, so it runs first on the way back, in tenancy `0028`, `0039`, `0040`, `0044`, `0045`, `0051`, `0052`, `0054`, `0059` and work `0034`; forward unchanged (no-op moved). `0020` has no refusal — the row named it in error | the ten migrations (🔒, review-ledger row) |

Eight new message keys, all eleven catalogues through `i18n_fanin.py`: `work.crews.member.onCrew`,
`work.technician.certifications.{col.proof, openProof, proofHelp, proofOnFile, proofType, proofTooLarge}`,
`work.technician.performance.closedAllTime`.

**Red first** (the tests written, then run with the source files as they stood on `8badcb01c`):
`crews2Lane.dom.test.tsx` 7 of 7 red — `expected null not to be null` (no names cell), `expected 'D. OrtizField technician · Invited'
to contain 'on Field crew A'`, the header `[Certification, Expires, Status, ""]` not `[…, Proof]`, `'Jobs closed1In All time…' to contain
'To date'`, `en: expected undefined to be truthy`; `test_def_wrk_9652_held_photo_gets_its_link.py` 3 of 4 red — `KeyError: 'upload_url'`
×2, `'NoneType' object is not subscriptable`; `test_def_ten_9655_rollback_refusal_runs_first.py` 11 red (ten files, each
*"refuse_rollback_over_live_rows is operation 1 of 3"*, and the repo-wide scan); `test_def_cus_9646_9648_named_refusals.py`
`KeyError: 'business'`, `500 == 422`, 18 × `500 == 404`, 9 × `422 == 404`. **Green:** the four files, plus
`crewsLane.dom.test.tsx` (one assertion moved: the count is no longer a text node of its own), vitest `src/features/work`,
`src/i18n`, `src/styles` 57 files, 647 passed; `tsc` and `eslint` clean; the sync/photo suites 110 passed on SQLite and
the PG-only ones 19 of 20 on PostgreSQL 16 (the 20th dated below).

**`DEF-TEN-9655` proved on PostgreSQL 16** (`sbh_wcrews2`, one `work_template_help` document stored): with `0059` as it
stood, `migrate tenancy 0058` failed on *`IntegrityError: check constraint "ck_stored_documents_source" … is violated by
some row`*; with the refusal moved last it answered *"refusing to roll back tenancy/0059: 1 stored_documents row(s) already
carry kind or source work_template_help. … Stay on this migration."*, both CHECKs still named the kind, and `migrate`
re-applied `tenancy 0060` and `work 0035–0037`. `makemigrations --check`: no changes.

**Walked on PostgreSQL 16 at 1440** (`10-scripts/cr168_crews2_walk.mjs`, `sbh_wcrews2`, seed_demo + load_sample_data, no
API response ≥ 400): `08-qa/work-2026-10-04/after/crews2-27-crews-member-names.png`, `crews2-26-person-list.png`,
`crews2-33-certifications-before.png`, `crews2-33-proof-refused.png`, `crews2-33-attach-pdf.png`,
`crews2-33-attach-photo.png`, `crews2-33-certifications-after.png` (read back: `first-aid-card.pdf` 193 bytes,
`traffic-card.png` 97 bytes, dates unchanged), `crews2-33-proof-opened.png` (200 `image/png`, `private, no-store`),
`crews2-34-performance-all-time.png` (*To date*).

**Exceptions (E4):** the member names are text, not the drawn link colour (decision log (1)); the row action is still
labelled *Renew* where image 33 draws *✎ Edit* — not this lane's change, left as lane CREWS built it.

**Reds I did not cause, dated on `8badcb01c`:** `test_def2030_2031_wizard_doors.py` — four cases red with
`customers.transfer.buyer_required` (they send no buyer), the same four on the tip; `test_us_wrk_044_sync_pg.py::test_044_the_batch_survives_a_REFUSAL_too_not_only_a_duplicate`
— expects *refused* where the server has HELD since FIELD-FIX (`ed1e5fa95`), filed `DEF-WRK-9659`.

**Rollback:** `2.516.0` → redeploy `2.515.0` (screens and the held-photo link only; no migration added — the ten reordered
migrations behave identically forward). `2.513.1` → redeploy `2.513.0`.

## 23 · Round 5 — lane RULES: the Rules list, the three-step builder and one rule's page (`2.515.0` · `2.516.1`)

Built from images 56–64 looked at as images (58 and 60 are the retired steps). Judgments: decision log *"CR-168 ROUND 5 ·
RULES"*. Side by side: `08-qa/work-2026-10-04/after/RULES-side-by-side.md`.

| Task / defect | What a user gets | Where |
|---|---|---|
| P3.16 · P3.60 · `DEF-WRK-9564` | *+ New rule* top right whatever the list holds | `RulesPage.tsx` |
| P3.18 · `DEF-WRK-9573` | The search asks the server (`GET /work/rules?q=`) — name, template, process words | `RulesPage.tsx`, `rules/ruleEndpoints.ts` |
| P3.63 | 👁 ✎ ⧉ on every row: the rule's page, its builder, a copy | `RulesPage.tsx` |
| P3.17 | Edit re-opens the builder on the rule (`…/rules/{id}/edit`, `?step=`); saving PATCHes | `RuleBuilder.tsx` |
| P3.19 · P3.64 · `DEF-WRK-5066` | Three steps — Trigger · Notify · Review — on `WizardFrame`; the census baseline line is deleted | `RuleBuilder.tsx`, `wizardRailCensus.test.ts` |
| ruling 10 · P3.65 | Twelve processes from `GET /work/rules/processes`, several triggers, each with its own settings (a quantity with its unit, a service's own units) | `RuleBuilder.tsx` `TriggerSettings` |
| P3.37 · P3.66 | *Who hears* rows: when, who, a message from Notifications' catalogue (by audience), how (its channels) | `RuleBuilder.tsx` `NotifyStep` |
| P3.67 | *When it stalls* rows: the seven kinds once each, hours, the derived *Who is told*, one *Also tell* (role or person), the kind's own message shown | same; `escalation_events` served by `rules.processes()` |
| P3.39 | The Review states *Tonight it raises N jobs* (`POST /work/rules/preview`, writes nothing) | `RuleBuilder.tsx` `ReviewStep` |
| P3.62 | One rule's page `/work/rules/{id}`: Overview (the same `RuleSummary` the Review draws, ✎ Edit per panel), Jobs, Audit; Edit · Duplicate · Turn off top right | `RuleDetailPage.tsx`, `rules/RuleSummary.tsx` |
| G98 | `Fact`, `FactList` unused in `TemplateDetailPage.tsx` removed | |

**Kit:** `TableArray` gains opt-in `footerLead` (a picker at the start of the footer row; B14 rule 36, first caller the
builder). **Recordings:** `work.rules.processes` re-recorded (`escalation_events`); `work.rules.lookup.notification-rules`,
`.services`, `.roles` recorded (the recorder gained them); all typed in `recordedServerShapes.typecheck.ts`.
**i18n:** 165 keys in all eleven catalogues in each language's own words, 23 retired (wave M's source/trigger words and
the five-step builder's), *Review & activate* → *Review*.

**Proof.** Red first on `3cd891cfb`: `rules/cr168Rules.dom.test.tsx` 10 of 10 red — *Unable to find … link "+ New rule"*,
*… "work.rules.action.open"*, *expected [ '/', … ] to include '/:tenant/work/rules/:ruleId'*, *expected 'Asset age
rule…' not to contain 'Backflow test due'* (the search), *expected null not to be null* (no WizardFrame), *Unable to find a
label … template*, and no rule page; `test_cr168_rules_lane_processes.py` red (`escalation_events` absent). After: 10
passed; vitest work + kit + i18n + routing 814 passed; backend 3 passed (SQLite); `tsc` clean; G98 PASS; G29 baseline +2
routes. **Walk on PostgreSQL 16** (`10-scripts/cr168_rules_after_walk.mjs`, 16/16): a rule built through the builder,
activated, swept — WO-0041, 0042, 0043 raised — its Jobs and Audit tabs opened, turned off, edit and duplicate opened.

**Filed, not this lane's to fix (server):** `DEF-WRK-9660` — a rule-raised asset job carries no premises, unit or account
(PREMISE is a dash on 63); `DEF-WRK-9661` — the preview promised 4, the sweep raised 3 (one subject refused, uncounted).

**Reds I did not cause, dated:** `wizardRailCensus` — `EDIT_INFO/CHANGE/CORRECT_STEPS` (`taxEditModel.ts`, since
`b71588e74`, red on `3cd891cfb` too). `run_gates --changed`: G103, G105, G106, G107, G114, G115, G116, G135 and the
standing set (G13, G15 backlog, G18, G33, G40 …) name no file of this lane.

**Rollback:** redeploy `2.514.0`. No migration.

**`2.516.1`:** the *If* picker on a *When it stalls* row no longer clips its words (*Nobody has picked it u*), found on
the walk's own shot of image 59 and re-shot; the walk script (`10-scripts/cr168_rules_after_walk.mjs`), the shots, the
side-by-side notes, this section and the decision-log row land with it. `DEF-WRK-9564`, `9573`, `5066` closed (fixed in
`e9c5e15df`). **Rollback:** redeploy `2.516.0`.

## 24 · Round 6 — lane SRV-5: the customer and the office are told, and work orders print (`2.517.0`)

Ruling 3 (PO, 23 Sep): *"Notification reaches the consumer and the back office, and work orders print."* Twelve judgments of
ours, none put to the PO (law 13) — the decision-log row of 2026-10-04 *"SRV-5 — TELL PEOPLE AND PRINT"* holds each with its
reasoning. Proved on SQLite and on PostgreSQL 16 (`config.settings.pgtest`, 28/28); walked at 1440 on PostgreSQL
(`10-scripts/cr168_srv5_walk.mjs`, 9/9), shots and the two PDFs in `08-qa/work-2026-10-04/after/srv5-*`.

| Item | What it does now | Where | Tests |
|---|---|---|---|
| P6.1 customer, four kinds | *booked* on the first assign/schedule with a time; *moved* once per NEW window; *on the way* on each depart (text); *done* when the office ACCEPTS a passed job — never at the field close, never for a failed one. Channels = the customer's election (`paperless` → email, `sms_reminders` → text) ∩ the utility's switch; nobody elected → no message and the act says so. Do-not-send holds, never drops | `work/visit_notices.py` → `notifications/work_customer_messages.py` (through `notifications_seam`) | `test_cr168_srv5_messages.py` |
| P6.1 templates | Four new seeded bodies: `service_visit_moved` (email), `sms_visit_booked`, `sms_visit_moved`, `sms_technician_on_the_way`; all filed as `service_appointment` under `OQ-1164` | `seed_templates.py`, `frozen_documents.py` | same + four count tests moved (catalogue 4→8, events 40→44, blocked 11→8, staff 15→18, listed 51→55, seeded 46→50, email 31→32, SMS 5→8) |
| P6.2 office, three kinds | *at risk* (hourly sweep, once per promise, only inside the utility's at-risk window), *declined by the technician*, *on hold* — in-app to whoever sent the job out + every System Admin, once each | `notifications/work_escalations.py`, `work/escalations.py` | `test_cr168_srv5_messages.py` |
| P6.3 print one order | **Print** in every shape of the order's head; a PDF through billing's one page writer, published unchanged as `billing/page_print.py` and reached by `billing_seam.page_engine()`. Premises address walked, customer read live, safety and tasks as boxes, readings with units, parts, sign-off; no database id in the bytes. On demand, deterministic | `work/print_docs.py`, `OrderDetailPage.tsx` | `test_cr168_srv5_print.py`, `orderPage.dom.test.tsx` |
| P6.4 day pack | **Print day…** on a technician's page (today by default): a cover list in order, then one sheet per open job that day; empty day prints *No open jobs on this day.* A crew's pack is served (`?crew=`) ~~with no screen door yet~~ — the door is on the Crews list since `2.518.0` (§27, `DEF-WRK-9672`) | `print_docs.py`, `PrintDayDialog.tsx`, `TechnicianDetailPage.tsx` | `PrintDayDialog.dom.test.tsx` |
| `DEF-NOT-9666` | Messages needing attention printed raw keys for six source kinds and two channels, and an in-app row's recipient as a user id. Words in eleven catalogues; `recipient_name` served for in-app rows only | `notifications/selectors.py`, `SettingsNotificationsTab.tsx` | `test_def_not_9666_queue_words.py` — red on `42e21fa89` (8 missing keys; `no attribute 'queue_recipient_name'`) |

**Existing utilities:** the four templates reach a utility provisioned earlier on its next `seed_notice_templates`
(`manage.py seed_demo --tenant <subdomain>`, insert-missing); until then its visit messages hold at dispatch with the
missing-template reason. *Booked*, *on the way* and *done* stay OFF there (stored off when drawn and refused) until a supervisor
switches them on. ~~**Gap stated, not ours:** text messages are written unaddressed (`recipient_not_resolvable`) — the
customer read holds no mobile number.~~ **Superseded `2.518.0` (§27, `DEF-NOT-9668`):** a text is addressed to the phone on
the account of a customer who chose texts. Journeys: `customer-told-about-a-visit.md`, `sla-breach.md` (P5.7).

**Rollback:** redeploy `2.516.5`. No migration; queued messages stay queued and are correct under both builds.

## 25 · Round 6 — lane I18N: every Work string in its own language (`2.516.2` …)

Scope (§8, R6 I18N): the Work strings rounds 2–5 added, judged in all ten non-English catalogues by B14 rule 35 and the
PO's test of 2026-10-04 (decision log *"A WORD SPELLED THE SAME AS ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER
ACTUALLY SAYS"*): **would a native speaker using a utility's back-office software say this word here?** Every catalogue
line was written through `10-scripts/i18n_fanin.py` (`allow_overwrite`), and each catalogue's diff is exactly the lines
in the tables below — nothing re-serialised around them. Every line, kept or replaced, is `NATIVE-REVIEW-OWED`
(B14 rule 35). Judgments: decision log *"CR-168 ROUND 6 · I18N"*.

**How the Work strings were read.** 1,768 `work.*` keys × 10 languages. Three sweeps, each a question a reader can
re-run: (a) every value still byte-identical to English (`G15`'s fresh list — 138 Work values); (b) every Latin word
inside a Hindi, Japanese or Korean Work value (11 hits, all `https`, `PDF`, `MB`, `YYYY-MM-DD` or the product name —
none carried over); (c) **one term per concept** — every short English label used by two or more Work keys, and every
catalogue that writes it two ways (562 pairs; most are grammatical gender or a noun beside its verb and stand). (c) is
what found the replacements below: the same act written with two words in one catalogue, one of them the English word
in another script.

### 25.1 · Ruling 1 — the eleven values for *Approvals*

The tab (`work.tabs.approvals`) and the page head (`work.approvals.title`) were already re-worded by lane ORDERS-LIST;
each was judged again here and **kept**: de *Freigaben* · es and es-MX *Aprobaciones* · fr-FR *Validations* (the
queue's own verb is *Valider*) · hi *मंज़ूरियाँ* · id-ID *Persetujuan* · it-IT *Approvazioni* · ja-JP *承認* · ko-KR *승인*
· pt-BR *Aprovações* — each the word that language's office staff use for a queue of things waiting to be signed off.
**What was not right was everything around them**: the queue's buttons and toasts used a second word for the act in
four languages, and in Korean that word (*수리*) reads first as *repair*. Those are the first rows of 25.2.

### 25.2 · Replaced — the spoken word, one term per concept (119 values, 53 keys)

| Key | Language | Old | New | Why |
|---|---|---|---|---|
| `work.approvals.accept` | de | {{order}} annehmen | **{{order}} abnehmen** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptConfirm` | de | Annehmen ✓ | **Abnehmen ✓** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptSelected_one` | de | Auswahl annehmen… ({{count}}) | **Auswahl abnehmen… ({{count}})** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptSelected_other` | de | Auswahl annehmen… ({{count}}) | **Auswahl abnehmen… ({{count}})** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptTitle` | de | {{order}} annehmen? | **{{order}} abnehmen?** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptTitleMany_one` | de | {{count}} Auftrag annehmen? | **{{count}} Auftrag abnehmen?** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptTitleMany_other` | de | {{count}} Aufträge annehmen? | **{{count}} Aufträge abnehmen?** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptedLive` | de | {{order}} angenommen · Sparte frei | **{{order}} abgenommen · Sparte frei** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptedMany_one` | de | {{count}} Auftrag angenommen | **{{count}} Auftrag abgenommen** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptedMany_other` | de | {{count}} Aufträge angenommen | **{{count}} Aufträge abgenommen** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptedOne` | de | {{order}} angenommen | **{{order}} abgenommen** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.acceptedSome` | de | {{done}} angenommen, {{failed}} abgelehnt | **{{done}} abgenommen, {{failed}} abgelehnt** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.note` | de | Jeder Auftrag hier hat Felddaten und wurde von niemandem angenommen. Wer einen annimmt, schaltet die Sparte frei und informiert den Kunden. | **Jeder Auftrag hier hat Felddaten und wurde von niemandem abgenommen. Wer einen abnimmt, schaltet die Sparte frei und informiert den Kunden.** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.sentence` | de | Der Außendienst hat diese abgeschlossen. Angenommen hat sie noch niemand. | **Der Außendienst hat diese abgeschlossen. Abgenommen hat sie noch niemand.** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.orders.kpi.awaiting` | de | Wartet auf Abnahme | **Wartet auf Freigabe** | *approval* is the tab's *Freigabe*; the tab, the empty state and the technician's list already say *Wartet auf Freigabe* |
| `work.order.approval.awaiting` | de | Wartet auf Abnahme | **Wartet auf Freigabe** | *approval* is the tab's *Freigabe*; the tab, the empty state and the technician's list already say *Wartet auf Freigabe* |
| `work.builder.readings.consequenceBody` | de | Ist es aktiv, geht der erfasste Wert in die Zählerhistorie, sobald die Vorgesetzte den Auftrag annimmt — datiert auf das Ende der Arbeit, nicht auf die Freigabe. | **Ist es aktiv, geht der erfasste Wert in die Zählerhistorie, sobald die Vorgesetzte den Auftrag abnimmt — datiert auf das Ende der Arbeit, nicht auf die Freigabe.** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.mobile.close.consequence` | de | Das Büro prüft das und nimmt es an. | **Das Büro prüft das und nimmt es ab.** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.technician.jobs.accepted` | de | Freigegeben | **Abgenommen** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.rules.process.failed_outcome` | de | Ein Auftrag wird als gescheitert angenommen | **Ein Auftrag wird als gescheitert abgenommen** | the office taking finished work is *abnehmen* (*die Abnahme*) — the order page's word; *annehmen* is the technician taking a job on the phone, so one act, one word |
| `work.approvals.accept` | ja-JP | {{order}} を受理 | **{{order}} を承認** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptConfirm` | ja-JP | 受理 ✓ | **承認する ✓** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptConsequenceNoBuild` | ja-JP | 現場の記録を受理します。 | **現場の記録を承認します。** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptSelected_one` | ja-JP | 選択分を受理… ({{count}}) | **選択分を承認… ({{count}})** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptSelected_other` | ja-JP | 選択分を受理… ({{count}}) | **選択分を承認… ({{count}})** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptTitle` | ja-JP | {{order}} を受理しますか？ | **{{order}} を承認しますか？** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptTitleMany_one` | ja-JP | {{count}} 件を受理しますか？ | **{{count}} 件を承認しますか？** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptTitleMany_other` | ja-JP | {{count}} 件を受理しますか？ | **{{count}} 件を承認しますか？** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptedLive` | ja-JP | {{order}} 受理 · 開通済み | **{{order}} 承認 · 開通済み** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptedMany_one` | ja-JP | {{count}} 件を受理しました | **{{count}} 件を承認しました** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptedMany_other` | ja-JP | {{count}} 件を受理しました | **{{count}} 件を承認しました** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptedOne` | ja-JP | {{order}} を受理しました | **{{order}} を承認しました** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.acceptedSome` | ja-JP | {{done}} 件受理、{{failed}} 件不可 | **{{done}} 件承認、{{failed}} 件不可** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.note` | ja-JP | ここにある作業指示には現場の記録があり、まだ誰も受理していません。受理するとそのサービスが開通し、お客さまに通知されます。 | **ここにある作業指示には現場の記録があり、まだ誰も承認していません。承認するとそのサービスが開通し、お客さまに通知されます。** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.approvals.sentence` | ja-JP | 現場での作業は完了しています。まだ誰も受理していません。 | **現場での作業は完了しています。まだ誰も承認していません。** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.builder.readings.consequenceBody` | ja-JP | 有効にすると、作業員が入力した値は上長が作業を受理した時点でメーターの計測履歴に入ります。日付は承認日ではなく作業を終えた日です。 | **有効にすると、作業員が入力した値は上長が作業を承認した時点でメーターの計測履歴に入ります。日付は承認日ではなく作業を終えた日です。** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.sync.job_already_accepted` | ja-JP | 受理後に送信されました。 | **承認後に送信されました。** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.rules.process.failed_outcome` | ja-JP | 作業が失敗として受理された | **作業が失敗として承認された** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.mobile.close.consequence` | ja-JP | 事務所が確認して受け付けます。 | **事務所が確認して承認します。** | *受理* is a filing-office word (a submitted form received); the tab, the order page and the badge say *承認* |
| `work.orders.acceptance.accepted` | ja-JP | 承諾済み | **受諾済み** | the technician's acceptance is *受諾* on the phone and in Rules; *承諾* was a second word for it |
| `work.orders.acceptance.pending` | ja-JP | 未承諾 | **未受諾** | the technician's acceptance is *受諾* on the phone and in Rules; *承諾* was a second word for it |
| `work.edit.action.cancelOrder` | ja-JP | オーダーを取り消す | **作業指示を取り消す** | *オーダー* is English *order* in katakana; every other Work screen says *作業指示* |
| `work.edit.confirm.body` | ja-JP | 誰も向かいません。オーダーの番号と履歴はそのまま残ります。 | **誰も向かいません。作業指示の番号と履歴はそのまま残ります。** | *オーダー* is English *order* in katakana; every other Work screen says *作業指示* |
| `work.edit.confirm.confirm` | ja-JP | オーダーを取り消す | **作業指示を取り消す** | *オーダー* is English *order* in katakana; every other Work screen says *作業指示* |
| `work.edit.description` | ja-JP | オーダー作成後に配車担当が変更するものはすべてここにあります。 | **作業指示の作成後に配車担当が変更するものはすべてここにあります。** | *オーダー* is English *order* in katakana; every other Work screen says *作業指示* |
| `work.edit.effects.technician` | ja-JP | 作業員の携帯 — オーダーはその場ですぐ変わります。 | **作業員の携帯 — 作業指示はその場ですぐ変わります。** | *オーダー* is English *order* in katakana; every other Work screen says *作業指示* |
| `work.edit.kicker` | ja-JP | 作業 › オーダー | **作業 › 作業指示** | *オーダー* is English *order* in katakana; every other Work screen says *作業指示* |
| `work.edit.loading` | ja-JP | オーダーを開いています | **作業指示を開いています** | *オーダー* is English *order* in katakana; every other Work screen says *作業指示* |
| `work.map.description` | ja-JP | 同じ未完了のオーダーを、作業する場所に置いて表示します。 | **同じ未完了の作業指示を、作業する場所に置いて表示します。** | *オーダー* is English *order* in katakana; every other Work screen says *作業指示* |
| `work.approvals.accept` | ko-KR | {{order}} 수리 | **{{order}} 승인** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptConfirm` | ko-KR | 수리 ✓ | **승인 ✓** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptConsequenceNoBuild` | ko-KR | 현장 기록이 수리됩니다. | **현장 기록이 승인됩니다.** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptSelected_one` | ko-KR | 선택 항목 수리… ({{count}}) | **선택 항목 승인… ({{count}})** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptSelected_other` | ko-KR | 선택 항목 수리… ({{count}}) | **선택 항목 승인… ({{count}})** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptTitle` | ko-KR | {{order}}을(를) 수리할까요? | **{{order}}을(를) 승인할까요?** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptTitleMany_one` | ko-KR | {{count}}건을 수리할까요? | **{{count}}건을 승인할까요?** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptTitleMany_other` | ko-KR | {{count}}건을 수리할까요? | **{{count}}건을 승인할까요?** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptedLive` | ko-KR | {{order}} 수리 · 서비스 개통 | **{{order}} 승인 · 서비스 개통** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptedMany_one` | ko-KR | {{count}}건 수리 완료 | **{{count}}건 승인 완료** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptedMany_other` | ko-KR | {{count}}건 수리 완료 | **{{count}}건 승인 완료** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptedOne` | ko-KR | {{order}} 수리 완료 | **{{order}} 승인 완료** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.acceptedSome` | ko-KR | {{done}}건 수리, {{failed}}건 거부 | **{{done}}건 승인, {{failed}}건 거부** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.note` | ko-KR | 여기 있는 작업 지시에는 현장 기록이 있으며 아직 아무도 수리하지 않았습니다. 수리하면 해당 서비스가 개통되고 고객에게 안내됩니다. | **여기 있는 작업 지시에는 현장 기록이 있으며 아직 아무도 승인하지 않았습니다. 승인하면 해당 서비스가 개통되고 고객에게 안내됩니다.** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.approvals.sentence` | ko-KR | 현장 작업은 끝났습니다. 아직 아무도 수리하지 않았습니다. | **현장 작업은 끝났습니다. 아직 아무도 승인하지 않았습니다.** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.mobile.close.consequence` | ko-KR | 사무실에서 확인하고 접수합니다. | **사무실에서 확인하고 승인합니다.** | *수리* reads first as *repair* in a work-order app; the tab and the order page say *승인* |
| `work.edit.action.cancelOrder` | ko-KR | 오더 취소 | **작업 지시 취소** | *오더* is English *order* in hangul; every other Work screen says *작업 지시* |
| `work.edit.confirm.body` | ko-KR | 아무도 가지 않으며, 오더의 번호와 이력은 그대로 남습니다. | **아무도 가지 않으며, 작업 지시의 번호와 이력은 그대로 남습니다.** | *오더* is English *order* in hangul; every other Work screen says *작업 지시* |
| `work.edit.confirm.confirm` | ko-KR | 오더 취소 | **작업 지시 취소** | *오더* is English *order* in hangul; every other Work screen says *작업 지시* |
| `work.edit.description` | ko-KR | 오더가 생긴 뒤 배차 담당이 바꾸는 것은 모두 여기 있습니다. | **작업 지시가 생긴 뒤 배차 담당이 바꾸는 것은 모두 여기 있습니다.** | *오더* is English *order* in hangul; every other Work screen says *작업 지시* |
| `work.edit.effects.technician` | ko-KR | 기사 휴대폰 — 오더가 바로 바뀝니다. | **기사 휴대폰 — 작업 지시가 바로 바뀝니다.** | *오더* is English *order* in hangul; every other Work screen says *작업 지시* |
| `work.edit.kicker` | ko-KR | 작업 › 오더 | **작업 › 작업 지시** | *오더* is English *order* in hangul; every other Work screen says *작업 지시* |
| `work.edit.loading` | ko-KR | 오더를 여는 중 | **작업 지시를 여는 중** | *오더* is English *order* in hangul; every other Work screen says *작업 지시* |
| `work.map.description` | ko-KR | 같은 진행 중 오더를 일하는 자리에 놓아 보여 줍니다. | **같은 진행 중 작업 지시를 일하는 자리에 놓아 보여 줍니다.** | *오더* is English *order* in hangul; every other Work screen says *작업 지시* |
| `work.orders.kpi.awaiting` | fr-FR | En attente d’acceptation | **En attente de validation** | the office's act is *valider* everywhere else (tab *Validations*, *Valider ✓*); *accepter* is the technician's |
| `work.builder.readings.consequenceBody` | fr-FR | Quand c’est actif, la valeur saisie entre dans l’historique du compteur dès que le superviseur accepte l’ordre — datée de la fin des travaux, pas de la validation. | **Quand c’est actif, la valeur saisie entre dans l’historique du compteur dès que le superviseur valide l’ordre — datée de la fin des travaux, pas de la validation.** | the office's act is *valider* everywhere else (tab *Validations*, *Valider ✓*); *accepter* is the technician's |
| `work.mobile.close.consequence` | fr-FR | Le bureau vérifie et accepte l’intervention. | **Le bureau vérifie et valide l’intervention.** | the office's act is *valider* everywhere else (tab *Validations*, *Valider ✓*); *accepter* is the technician's |
| `work.orders.kpi.awaitingSub` | fr-FR | Travail fait, personne n’a accepté | **Travail fait, personne n’a validé** | the office's act is *valider* everywhere else (tab *Validations*, *Valider ✓*); *accepter* is the technician's |
| `work.sync.job_already_accepted` | fr-FR | Envoyé après l’acceptation. | **Envoyé après la validation.** | the office's act is *valider* everywhere else (tab *Validations*, *Valider ✓*); *accepter* is the technician's |
| `work.rules.process.failed_outcome` | fr-FR | Une intervention est acceptée comme échouée | **Une intervention est validée comme échouée** | the office's act is *valider* everywhere else (tab *Validations*, *Valider ✓*); *accepter* is the technician's |
| `work.orders.kpi.awaiting` | es | Pendiente de aceptar | **Pendiente de aprobación** | the same *Awaiting approval* was written two ways in one catalogue; the order page's words win |
| `work.technician.jobs.accepted` | es | Aprobado | **Aceptada** | the same *Accepted* (the office took the job) as the order page |
| `work.orders.kpi.awaiting` | es-MX | Pendiente de aceptar | **Pendiente de aprobación** | the same *Awaiting approval* was written two ways in one catalogue; the order page's words win |
| `work.technician.jobs.accepted` | es-MX | Aprobado | **Aceptada** | the same *Accepted* (the office took the job) as the order page |
| `work.orders.kpi.awaiting` | it-IT | In attesa di accettazione | **In attesa di approvazione** | the same *Awaiting approval* was written two ways in one catalogue; the order page's words win |
| `work.technician.jobs.accepted` | it-IT | Approvato | **Accettato** | the same *Accepted* (the office took the job) as the order page |
| `work.orders.kpi.awaiting` | pt-BR | Aguardando aceite | **Aguardando aprovação** | the same *Awaiting approval* was written two ways in one catalogue; the order page's words win |
| `work.technician.jobs.accepted` | pt-BR | Aprovado | **Aceita** | the same *Accepted* (the office took the job) as the order page |
| `work.templates.col.service` | pt-BR | Utilidade | **Serviço** | *Utilidade* is *utility* word for word; the English is *Service* and Work writes *Serviço* |
| `work.templates.filter.service` | pt-BR | Utilidade | **Serviço** | *Utilidade* is *utility* word for word; the English is *Service* and Work writes *Serviço* |
| `work.orders.kpi.awaiting` | hi | स्वीकृति बाकी | **मंज़ूरी बाकी** | the same *Awaiting approval* was written two ways in one catalogue; the order page's words win |
| `work.technician.jobs.accepted` | hi | मंज़ूर | **स्वीकृत** | the same *Accepted* (the office took the job) as the order page |
| `work.unassigned` | hi | अनासाइन | **किसी को नहीं सौंपा** | *अनासाइन* is English *unassign* in Devanagari; two siblings already say *किसी को नहीं सौंपा* |
| `work.technician.jobs.accepted` | id-ID | Disetujui | **Diterima** | the office's act is *terima* on the order page and the queue; *disetujui* was a second word |
| `work.orders.kpi.awaitingSub` | id-ID | Sudah dikerjakan, belum disetujui | **Sudah dikerjakan, belum diterima** | the office's act is *terima* on the order page and the queue; *disetujui* was a second word |
| `work.edit.action.cancelOrder` | id-ID | Batalkan order | **Batalkan perintah kerja** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.edit.confirm.body` | id-ID | Tidak ada yang dikirim, dan order tetap punya nomor serta riwayatnya. | **Tidak ada yang dikirim, dan perintah kerja tetap punya nomor serta riwayatnya.** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.edit.confirm.confirm` | id-ID | Batalkan order | **Batalkan perintah kerja** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.edit.description` | id-ID | Semua yang diubah petugas setelah order sudah ada. | **Semua yang diubah petugas setelah perintah kerja dibuat.** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.edit.effects.technician` | id-ID | Ponsel teknisi — order langsung berubah di sana. | **Ponsel teknisi — perintah kerja langsung berubah di sana.** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.edit.kicker` | id-ID | KERJA › ORDER | **PEKERJAAN › PERINTAH KERJA** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.edit.loading` | id-ID | Membuka order | **Membuka perintah kerja** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.map.cluster.label_one` | id-ID | {{count}} order di {{address}} | **{{count}} perintah kerja di {{address}}** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.map.cluster.label_other` | id-ID | {{count}} order di {{address}} | **{{count}} perintah kerja di {{address}}** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.map.cluster.title_one` | id-ID | {{count}} order di lokasi ini | **{{count}} perintah kerja di lokasi ini** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.map.cluster.title_other` | id-ID | {{count}} order di lokasi ini | **{{count}} perintah kerja di lokasi ini** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.map.description` | id-ID | Order terbuka yang sama, diletakkan di tempat kerjanya. | **Perintah kerja terbuka yang sama, diletakkan di tempat kerjanya.** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.map.empty` | id-ID | Belum ada order di daftar ini yang punya tempat di peta. | **Belum ada perintah kerja di daftar ini yang punya tempat di peta.** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.map.unplaced.help` | id-ID | Order ini nyata; petanya yang belum punya tempat. | **Perintah kerja ini nyata; petanya yang belum punya tempat.** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.map.unplaced.title_one` | id-ID | TIDAK DI PETA · {{count}} ORDER | **TIDAK DI PETA · {{count}} PERINTAH KERJA** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.map.unplaced.title_other` | id-ID | TIDAK DI PETA · {{count}} ORDER | **TIDAK DI PETA · {{count}} PERINTAH KERJA** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.order.cancel.confirm` | id-ID | Batalkan order ini | **Batalkan perintah kerja ini** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.order.cancel.done` | id-ID | Order dibatalkan. | **Perintah kerja dibatalkan.** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.order.cancel.keep` | id-ID | Simpan order | **Pertahankan perintah kerja** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.order.hold.done` | id-ID | Order ditahan. | **Perintah kerja ditahan.** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.orders.atPlace.searchAccount` | id-ID | Cari nomor order, jenis, atau teknisi… | **Cari nomor perintah, jenis, atau teknisi…** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.orders.col.orderNo` | id-ID | No. order | **No. perintah** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.technician.jobs.search` | id-ID | Cari order, alamat… | **Cari nomor perintah, alamat…** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.template.ordersRaised_one` | id-ID | {{count}} order dibuat | **{{count}} perintah kerja dibuat** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |
| `work.template.ordersRaised_other` | id-ID | {{count}} order dibuat | **{{count}} perintah kerja dibuat** | *order* is English carried over; lane WORDS ruled *perintah (kerja)* and the Orders list says it |

### 25.3 · Kept — same spelling as English, and what a native speaker says (138 Work values)

Each is on `G15`'s per-language list (or, for the six strings with no word of any language in them, `UNIVERSAL`) with
its reason in the gate's own comment. `G15` exempts by VALUE within a language, so the same judgment also cleared
twelve values outside Work that carry the identical text — listed after the table, so the count is honest.

| Key | Languages | Value | Kept | Why |
|---|---|---|---|---|
| `work.builder.help.sizeKb` | de es es-MX hi id-ID it-IT ja-JP ko-KR pt-BR | {{count}} KB | kept | the unit symbol each of these writes for a file size; French alone writes *Ko*, and its catalogue does |
| `work.builder.help.sizeMb` | de es es-MX hi id-ID it-IT ja-JP ko-KR pt-BR | {{size}} MB | kept | as above (French *Mo*) |
| `work.builder.row.cell` | all ten | {{column}} {{row}} | kept (`UNIVERSAL`) | a box's accessible name: its column's own label and a row number — no word to translate |
| `work.builder.help.kind.link` | de it-IT pt-BR | Link | kept | *der Link*, *il link*, *o link* — what each says; es *Enlace*, fr *Lien* stay theirs |
| `work.template.versionsCount_one` / `_other` | fr-FR | {{count}} version / versions | kept | *une version* is French; the catalogue already keeps *Version* |
| `work.template.tab.versions` | fr-FR | Versions | kept | as above |
| `work.template.col.version` | de | Version | kept | *die Version* is German |
| `work.order.overview.versionValue` | de es es-MX hi | v{{version}} | kept | the version prefix six other catalogues already keep |
| `work.template.version` | es es-MX hi | v{{version}} | kept | as above |
| `work.edit.title`, `work.order.title` | all ten | {{order}} · {{type}} | kept (`UNIVERSAL`) | an order number and a job type's name, both the tenant's own |
| `work.edit.holder` | all ten | {{name}} · {{kind}} | kept (`UNIVERSAL`) | a holder's name and kind, joined by a dot |
| `work.mobile.photos.row` | all ten | {{taken}} · {{device}} | kept (`UNIVERSAL`) | a photo's time and device, joined by a dot |
| `work.edit.window.morning` / `.afternoon` | all ten | 08:00–12:00 / 12:00–17:00 | kept (`UNIVERSAL`) | a 24-hour window, written so in every one of the ten |
| `work.fieldVisit.minutes_one` / `_other`, `work.mobile.card.minutes`, `work.templates.minutes` | es es-MX fr-FR it-IT pt-BR | {{count}} min | kept | lane WORDS' *min* judgment (§19.2), same abbreviation |
| `work.order.tasks.minutes` | es es-MX fr-FR it-IT pt-BR | {{minutes}} min | kept | as above |
| `work.builder.readings.col.min` | fr-FR id-ID it-IT | Min | kept | the abbreviation of *minimum* in each (Indonesian pairs it with *Maks*) |
| `work.builder.readings.col.max` | fr-FR it-IT | Max | kept | the abbreviation of *maximum* |
| `work.fieldVisit.col.module` | fr-FR | Module | kept | *un module* |
| `work.orders.dispatch.en_route` | fr-FR | En route | kept | French, and what a French dispatcher says of a technician on the way |
| `work.order.readings.optional` | de | Optional | kept | *optional* is German |
| `work.pill.routine` | de | Routine | kept | *Routine* beside *Dringend* is what a German dispatcher writes on a routine job |
| `work.order.checklist.title`, `work.order.tabs.checklist` | pt-BR | Checklist | kept | *o checklist* is what a Brazilian field team says; the page's own sentence already reads *não tem checklist* |

**Cleared outside Work by the same value (12):** de `customers.account.field.planVersion`,
`customers.newConnect.step7.colVersion` (*Version*), `rating.rs.wiz.optional` (*Optional*),
`integrations.keys.versionSuffix` (*v{{version}}*, also in es, es-MX, hi); `billing.runs.tile.minutes` (*{{count}} min*)
in es, es-MX, fr-FR, it-IT, pt-BR — each the same word in the same language, so the same judgment holds.

**Count after this push.** `G15` fresh (`DEF-GOV-9597`): **819 → 669** — 138 Work values kept with reasons, 12 cleared
outside Work by the same values; the 119 replacements were not in the 819 (they were already in their language's
script, but in the wrong word). `work.*` values left in `G15`'s fresh list: **0**.

**Rollback:** redeploy `2.516.1`; no data moves (catalogue text and a gate allow list only).

### 25.4 · The customer class, and a word that meant *advertisement* (`DEF-CUS-9662`, `2.516.3`)

Reading the backlog for item 4 found a value that was translated and WRONG, which `G15` cannot see: the account
category *Commercial* read **광고** (*advertisement*) in Korean and **コマーシャル** (a TV commercial) in Japanese, and the
same on a unit's type. Rating's customer-class picker printed English in five catalogues, and the same four classes
were written two or three ways inside one catalogue. Filed `DEF-CUS-9662` first; `src/i18n/customerClassOneWord.test.ts`
was **red on `ceb0953c7`** — 11 failing cases (de, es-MX, fr-FR, hi, id-ID, it-IT, ja-JP ×2, ko-KR ×2, pt-BR; es alone
already agreed), e.g. *"customers.accounts.category.commercial = コマーシャル (want 商業)"* — and green after. The
reference is the tax wizard's word, except in Japanese, where the tariff form *住宅用 · 商業用 · 産業用* is what a
Japanese utility prints and the wizard moves to it. A unit's TYPE is a dwelling, not a customer (German keeps *Wohnen*
there), so the test checks it only for the advertisement word. Its rows are in 25.5.

### 25.5 · Item 4 — the rest of `G15`'s backlog (`DEF-GOV-9597`), every value judged (`2.516.3`)

669 fresh values outside Work at the start of this push: **48 replaced** and **621 kept** (second table). The
replaced table holds 68 rows: the 48, plus 20 values that were already in their language but in a second or wrong
word — the customer-class rows of 25.4 and the Indonesian *pensiun* line (a person's retirement, not a discount's). Nothing was guessed: every value is either the word the language uses here or a string with no word in
it; the four patterns French, German or Japanese write differently (a percent sign, a colon before an amount, a
month-year) are kept only in the catalogues that write them the English way.

**Replaced (68 values, 25 keys):**

| Key | Language | Old | New | Why |
|---|---|---|---|---|
| `customers.accounts.category.residential` | de | Wohnen | **Privatkunden** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `rating.discounts.ends_after_retire` | de | It ends after the retire date. | **Endet nach dem Auslaufdatum.** | an English sentence pasted into every catalogue; written as its sibling *starts after the retire date* already is, with the same word for the retire date |
| `customers.newAccount.unit.squareFeet` | de | {{value}} sq ft | **{{value}} Quadratfuß** | *sq ft* is English; written as `metering.units.sqFt` already writes the same area |
| `rating.customerClass.residential` | es-MX | Residential | **Residencial** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `customers.accounts.category.residential` | es-MX | Uso residencial | **Residencial** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `rating.customerClass.commercial` | es-MX | Commercial | **Comercial** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `customers.accounts.category.commercial` | es-MX | Uso comercial | **Comercial** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `customers.accounts.category.industrial` | es-MX | Uso industrial | **Industrial** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `rating.customerClass.government` | es-MX | Government | **Gobierno** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `customers.accounts.category.government` | es-MX | Sector público | **Gobierno** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `rating.discounts.ends_after_retire` | es-MX | It ends after the retire date. | **Termina después de la fecha de retiro.** | an English sentence pasted into every catalogue; written as its sibling *starts after the retire date* already is, with the same word for the retire date |
| `customers.newAccount.unit.squareFeet` | es-MX | {{value}} sq ft | **{{value}} pies²** | *sq ft* is English; written as `metering.units.sqFt` already writes the same area |
| `customers.accounts.category.government` | fr-FR | Gouvernement | **Administrations** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `rating.discounts.ends_after_retire` | fr-FR | It ends after the retire date. | **Se termine après la date de retrait.** | an English sentence pasted into every catalogue; written as its sibling *starts after the retire date* already is, with the same word for the retire date |
| `customers.newAccount.unit.squareFeet` | fr-FR | {{value}} sq ft | **{{value}} pi²** | *sq ft* is English; written as `metering.units.sqFt` already writes the same area |
| `rating.customerClass.residential` | hi | Residential | **आवासीय** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.customerClass.commercial` | hi | Commercial | **वाणिज्यिक** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.customerClass.industrial` | hi | Industrial | **औद्योगिक** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.customerClass.government` | hi | Government | **सरकारी** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.discounts.ends_after_retire` | hi | It ends after the retire date. | **यह समाप्ति तिथि के बाद ख़त्म होती है।** | an English sentence pasted into every catalogue; written as its sibling *starts after the retire date* already is, with the same word for the retire date |
| `rating.customerClass.residential` | id-ID | Residential | **Rumah tangga** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `customers.accounts.category.residential` | id-ID | Perumahan | **Rumah tangga** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `rating.customerClass.commercial` | id-ID | Commercial | **Komersial** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.customerClass.industrial` | id-ID | Industrial | **Industri** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.customerClass.government` | id-ID | Government | **Pemerintah** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.discounts.ends_after_retire` | id-ID | It ends after the retire date. | **Berakhir setelah tanggal penghentian.** | an English sentence pasted into every catalogue; written as its sibling *starts after the retire date* already is, with the same word for the retire date |
| `rating.discounts.starts_after_retire` | id-ID | Mulai setelah tanggal pensiun diskon. | **Mulai setelah tanggal penghentian.** | *tanggal pensiun* is a person's retirement date, word for word; a retired discount is *dihentikan* (the status pill's word) |
| `customers.newAccount.unit.squareFeet` | id-ID | {{value}} sq ft | **{{value}} kaki²** | *sq ft* is English; written as `metering.units.sqFt` already writes the same area |
| `metering.upload.result.rollback` | id-ID | Rollback | **Pembatalan** | *rollback* is IT jargon a clerk does not say; the upload is undone (*dibatalkan*) |
| `customers.accounts.category.government` | it-IT | Governo | **Pubblica amministrazione** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `rating.discounts.ends_after_retire` | it-IT | It ends after the retire date. | **Finisce dopo la data di ritiro.** | an English sentence pasted into every catalogue; written as its sibling *starts after the retire date* already is, with the same word for the retire date |
| `customers.newAccount.unit.squareFeet` | it-IT | {{value}} sq ft | **{{value}} piedi²** | *sq ft* is English; written as `metering.units.sqFt` already writes the same area |
| `billing.bill.channel.email` | it-IT | Email | **E-mail** | the catalogue writes *E-mail* in 33 places; one spelling (lane WORDS' judgment, §19.2) |
| `billing.bill.field.email` | it-IT | Email | **E-mail** | the catalogue writes *E-mail* in 33 places; one spelling (lane WORDS' judgment, §19.2) |
| `customers.finder.col.email` | it-IT | Email | **E-mail** | the catalogue writes *E-mail* in 33 places; one spelling (lane WORDS' judgment, §19.2) |
| `customers.serviceRequest.messages.channel.email` | it-IT | Email | **E-mail** | the catalogue writes *E-mail* in 33 places; one spelling (lane WORDS' judgment, §19.2) |
| `customers.transfer.msg.email` | it-IT | Email | **E-mail** | the catalogue writes *E-mail* in 33 places; one spelling (lane WORDS' judgment, §19.2) |
| `portal.signIn.email` | it-IT | Email | **E-mail** | the catalogue writes *E-mail* in 33 places; one spelling (lane WORDS' judgment, §19.2) |
| `portal.preferences.column.email` | it-IT | EMAIL | **E-MAIL** | as *E-mail*, in the column's capitals |
| `rating.rs.wiz.col.asset` | it-IT | Asset | **Impianto** | *asset* is English; the one-time bill's same column says *Impianto* |
| `rating.customerClass.residential` | ja-JP | Residential | **住宅用** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.taxWiz.classes.residential` | ja-JP | 住宅 | **住宅用** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `rating.customerClass.commercial` | ja-JP | Commercial | **商業用** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.taxWiz.classes.commercial` | ja-JP | 商業 | **商業用** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `customers.accounts.category.commercial` | ja-JP | コマーシャル | **商業用** | *コマーシャル* is a TV commercial; a commercial customer is *商業用* (`DEF-CUS-9662`) |
| `rating.customerClass.industrial` | ja-JP | Industrial | **産業用** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.taxWiz.classes.industrial` | ja-JP | 工業 | **産業用** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `rating.customerClass.government` | ja-JP | Government | **官公庁** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `customers.accounts.category.government` | ja-JP | 政府 | **官公庁** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `metering.units.type.commercial` | ja-JP | コマーシャル | **商業用** | *コマーシャル* is a TV commercial; a commercial unit is *商業用* (`DEF-CUS-9662`) |
| `rating.discounts.ends_after_retire` | ja-JP | It ends after the retire date. | **廃止日より後に終わります。** | an English sentence pasted into every catalogue; written as its sibling *starts after the retire date* already is, with the same word for the retire date |
| `customers.newAccount.unit.squareFeet` | ja-JP | {{value}} sq ft | **{{value}} 平方フィート** | *sq ft* is English; written as `metering.units.sqFt` already writes the same area |
| `rating.customerClass.residential` | ko-KR | Residential | **주거용** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.customerClass.commercial` | ko-KR | Commercial | **상업용** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `customers.accounts.category.commercial` | ko-KR | 광고 | **상업용** | *광고* is *advertisement*; a commercial customer is *상업용* (`DEF-CUS-9662`) |
| `rating.customerClass.industrial` | ko-KR | Industrial | **산업용** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `rating.customerClass.government` | ko-KR | Government | **관공서** | English carried over in Rating's customer-class picker; now the tax wizard's word (`DEF-CUS-9662`) |
| `customers.accounts.category.government` | ko-KR | 정부 | **관공서** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `metering.units.type.commercial` | ko-KR | 광고 | **상업용** | *광고* is *advertisement*; a commercial unit is *상업용* (`DEF-CUS-9662`) |
| `rating.discounts.ends_after_retire` | ko-KR | It ends after the retire date. | **종료일 이후에 끝납니다.** | an English sentence pasted into every catalogue; written as its sibling *starts after the retire date* already is, with the same word for the retire date |
| `customers.newAccount.unit.squareFeet` | ko-KR | {{value}} sq ft | **{{value}} 제곱피트** | *sq ft* is English; written as `metering.units.sqFt` already writes the same area |
| `customers.accounts.category.industrial` | pt-BR | Industriais | **Industrial** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `customers.accounts.category.government` | pt-BR | Governo | **Poder público** | one word per customer class in the catalogue (`DEF-CUS-9662`): Rating's picker, the tax wizard and the account category now agree |
| `rating.discounts.ends_after_retire` | pt-BR | It ends after the retire date. | **Termina após a data de retirada.** | an English sentence pasted into every catalogue; written as its sibling *starts after the retire date* already is, with the same word for the retire date |
| `customers.newAccount.unit.squareFeet` | pt-BR | {{value}} sq ft | **{{value}} pés²** | *sq ft* is English; written as `metering.units.sqFt` already writes the same area |
| `reports.scheduled.column.status` | pt-BR | Status | **Situação** | Reports says *Situação* in every other status column; one word |
| `rating.discounts.ends_after_retire` | es | It ends after the retire date. | **Termina después de la fecha de retiro.** | an English sentence pasted into every catalogue; written as its sibling *starts after the retire date* already is, with the same word for the retire date |
| `customers.newAccount.unit.squareFeet` | es | {{value}} sq ft | **{{value}} pies²** | *sq ft* is English; written as `metering.units.sqFt` already writes the same area |

**Kept (621 values):**

| Value | Languages | Keys | Why |
|---|---|---|---|
| ${{amount}} | es es-MX hi id-ID | `portal.equipment.perMonth`, `portal.usage.costTotal` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| ({{current}} − {{prior}}) × {{multiplier}} = {{usage}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR | `metering.read.mathLine` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| + API | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `integrations.customApi.addButton` | a file format or industry acronym, written so in each (`UNIVERSAL`) |
| + Correction | fr-FR | `payments.correction.action` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| + Service | fr-FR | `customers.serviceRequest.services.addService` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| 1 cycle | fr-FR | `billing.runs.tile.runsDetail_one` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| 1 meter | id-ID | `metering.fieldVisit.meterCount_one` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| 1–30 | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `finance.aging.band.1-30`, `finance.aging.col.d1_30` | an ageing band: numbers (`UNIVERSAL`) |
| 31–60 | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `finance.aging.band.31-60`, `finance.aging.col.d31_60` | an ageing band: numbers (`UNIVERSAL`) |
| 61–90 | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `finance.aging.band.61-90`, `finance.aging.col.d61_90` | an ageing band: numbers (`UNIVERSAL`) |
| 90+ | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `finance.aging.band.90+`, `finance.aging.col.d90_plus` | an ageing band: numbers (`UNIVERSAL`) |
| AC-2026-00027 | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `portal.enrol.accountNumberExample` | sample data shown in a field (`UNIVERSAL`) |
| ACH | es es-MX hi id-ID | `customers.deposit.method.ach` | a file format or industry acronym, written so in each (`UNIVERSAL`) |
| APIs | de pt-BR | `integrations.column.apis` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Bank | de id-ID | `customers.serviceRequest.capture.chequeBank` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Batch | id-ID | `metering.upload.result.panel.batch`, `payments.col.batch` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| billing@yourutility.example | ja-JP ko-KR | `integrations.modal.emailExample` | sample data shown in a field (`UNIVERSAL`) |
| BL-2608-0141 | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `portal.quickPay.billNumberExample` | sample data shown in a field (`UNIVERSAL`) |
| Block | de | `rating.rate.review.col.block` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Budget | de fr-FR it-IT | `rating.discountForm.review.budget` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Classes | pt-BR | `rating.taxForm.summary.classes` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Communication | fr-FR | `customers.newConnect.step1.communication`, `customers.newConnect.step7.colMessage` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Composition | fr-FR | `metering.upload.post.panel.composition`, `metering.upload.result.panel.composition` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Confirmation | fr-FR | `finance.taxes.paid.col.confirmation` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Confirmations | fr-FR | `portal.preferences.kind.account` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Contact | fr-FR | `customers.capture.group.reach`, `customers.newConnect.step7.contact` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Correction | fr-FR | `rating.rateDetail.versions.isCorrection`, `rating.rs.wiz.correction` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| CSV | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `reports.schedule.format.csv`, `settings.rules.choice.default_download_format.csv` | a file format or industry acronym, written so in each (`UNIVERSAL`) |
| Cycle · {{frequency}} | fr-FR | `metering.cycleDetail.kicker` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Dates | fr-FR | `assets.upload.group.dates`, `billing.bill.panel.dates` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Debit | id-ID | `finance.entryDetail.col.debit`, `reports.col.debit`, `reports.kpi.debit` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Deposit | id-ID | `customers.deposit.field.decision`, `customers.deposit.totals.deposit`, `customers.moveIn.step.deposit`, `customers.newAccount.title.deposit` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Digital | de es es-MX id-ID pt-BR | `payments.source.webhook` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| DOCUMENTS | fr-FR | `portal.kicker.documents` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| DSO | de es es-MX fr-FR id-ID it-IT ja-JP ko-KR pt-BR | `reports.col.dso`, `reports.kpi.dso` | a file format or industry acronym, written so in each (`UNIVERSAL`) |
| ERP | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `integrations.category.erp` | a file format or industry acronym, written so in each (`UNIVERSAL`) |
| est. | es es-MX | `customers.account.usage.estimatedMark` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Export | de fr-FR | `finance.export.headTitle`, `finance.export.view.export` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Federal | id-ID | `rating.taxes.level.federal` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| File | it-IT | `customers.account.documents.field.file`, `customers.serviceRequest.capture.col.file`, `customers.serviceRequest.documents.col.file`, `finance.export.col.file`, `metering.read.compliance.file`, `reports.col.file_name`, `reports.history.column.file`, `reports.value.source_kind.csv` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Format | de fr-FR id-ID | `reports.schedule.format` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Hash | es es-MX id-ID it-IT pt-BR | `metering.read.compliance.hash` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Home | it-IT | `portal.tab.home` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Imports | fr-FR | `reports.kpi.imports` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Industrial | es-MX pt-BR | `rating.customerClass.industrial` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Item | id-ID pt-BR | `rating.rs.wiz.col.item` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Label | id-ID | `customers.newAccount.field.unitLabel`, `rating.discountForm.summary.label` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Latitude | fr-FR pt-BR | `customers.newConnect.step3.latitude`, `metering.premises.field.lat` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Lift | id-ID | `metering.commonAreas.kind.lift` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Lockbox | id-ID | `customers.deposit.method.lockbox` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Longitude | fr-FR pt-BR | `customers.newConnect.step3.longitude`, `metering.premises.field.lng` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Manual | es es-MX id-ID pt-BR | `reports.value.source_kind.manual`, `runbooks.mine.trigger.manual` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Memo | id-ID | `finance.entryDetail.memo` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Message | fr-FR | `customers.account.communication.field.body`, `customers.serviceRequest.messages.col.message` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Messages | fr-FR | `customers.newConnect.review.messages`, `portal.shell.messages` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Meter {{label}} | id-ID | `billing.oneTimeBill.services.asset.meter` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Minimum | fr-FR id-ID | `customers.newConnect.step3.col.minimum`, `rating.rs.col.minimum` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Mode | fr-FR | `customers.connection.order.mode` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Model | id-ID | `assets.form.model` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Net | fr-FR | `billing.fix.bulk.answer.net` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| No. | id-ID | `portal.planOffer.colNumber` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| NOTE | fr-FR | `payments.correction.notChangedTag` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Notes | fr-FR | `metering.units.account.sectionNotes` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Occupant | fr-FR | `customers.disconnect.check.colOccupant`, `metering.units.col.occupant`, `reports.col.occupant` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Occupants | fr-FR | `customers.reconnect.fact.occupants` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Option | de fr-FR | `customers.moveRecord.option.option` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| optional | de | `metering.addUnits.section.optional`, `metering.premises.section.optional` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Options | fr-FR | `customers.moveRecord.section.whereItCouldGo` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Pages | fr-FR | `billing.print.col.pages`, `billing.print.tile.pages` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Password | it-IT | `portal.signIn.password` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Per {{unit}} | id-ID it-IT | `billing.oneTimeBill.bill.charge.perUnit` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Platform | id-ID | `runbooks.category.platform` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Point | fr-FR | `metering.premises.point.row` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Points | fr-FR | `customers.disconnect.choose.colPoints` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Portal | es es-MX id-ID pt-BR | `customers.account.communication.channel.portal` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Post | de | `customers.serviceRequest.messages.channel.post` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Postmark | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `integrations.provider.postmark.name` | a provider's own name (`UNIVERSAL`) |
| Protection | fr-FR | `customers.disconnect.check.colProtection` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Question | fr-FR | `customers.disconnectRecord.check.col.question` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Register | id-ID | `assets.usage.registerLabel`, `customers.moveIn.reads.col.register`, `metering.estimate.channel`, `metering.estimate.channelLabel`, `metering.reads.col.channel`, `metering.reads.filter.channel`, `metering.routeReads.filter.register`, `rating.rs.usage.register` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Report | it-IT | `reports.custom.column.report`, `reports.edit.section.report`, `reports.history.column.report`, `reports.scheduled.column.report` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Route {{route}} — {{name}} | de | `metering.premises.route.named` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Route · {{name}} | de | `metering.routeReads.kicker` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| SendGrid | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `integrations.provider.sendgrid.name` | a provider's own name (`UNIVERSAL`) |
| Services | fr-FR | `customers.disconnect.choose.factServices`, `customers.disconnect.confirm.factServices`, `customers.disconnectRecord.cutDialog.services`, `customers.newConnect.context.services`, `customers.reconnect.fact.services`, `customers.serviceRequest.capture.services`, `customers.transfer.fact.services`, `finance.revenue.view.services`, `metering.premises.col.servicesShort`, `metering.units.services.label`, `portal.accounts.colServices`, `portal.enrol.services`, `rating.discountForm.field.services`, `rating.discounts.servicesLabel`, `reports.saveAs.services` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Session | fr-FR | `metering.read.compliance.session` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Sessions | fr-FR | `settings.security.sessions` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| SMS | de es es-MX fr-FR id-ID it-IT ja-JP pt-BR | `customers.paymentPlan.channel.sms` | a file format or industry acronym, written so in each (`UNIVERSAL`) |
| Standard | de fr-FR it-IT | `integrations.customApi.standard`, `reports.library.tab.standard` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Sub | es es-MX id-ID pt-BR | `customers.moveIn.reads.tag.sub` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Target | id-ID | `reports.col.target` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Total | es es-MX id-ID | `billing.fix.col.total`, `customers.moveIn.reads.register.total`, `customers.newConnect.charges.total`, `finance.aging.col.total`, `payments.debtor.col.total`, `payments.reapply.col.total` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Version {{version}} | de | `common.buildVersion` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| Zero | it-IT pt-BR | `rating.rate.review.minimumZero` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{category}} · {{plan}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `customers.disconnect.confirm.planAndCategory` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{count, number}} unit | id-ID | `billing.bulkRun.notInRun.headUnits_one` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{count}} API | de es es-MX fr-FR hi id-ID it-IT pt-BR | `integrations.card.apis_one` | a file format or industry acronym, written so in each (`UNIVERSAL`) |
| {{count}} APIs | de pt-BR | `integrations.card.apis_other` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{count}} classes | pt-BR | `rating.chargeCode.pricedBy.base.some` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{count}} cycles | fr-FR | `billing.runs.tile.runsDetail_other` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{count}} document | fr-FR | `portal.documents.count_one` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{count}} documents | fr-FR | `portal.documents.count_other` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{count}} minute | fr-FR | `settings.security.optionMinutes_one` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{count}} minutes | fr-FR | `settings.security.optionMinutes_other` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{from}}–{{to}} | de es es-MX fr-FR hi id-ID it-IT pt-BR | `portal.usage.nextReadingRange` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{kind}} · {{size}} | de es es-MX fr-FR hi id-ID it-IT ko-KR pt-BR | `portal.equipment.kindWithSize` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{kw}} kW | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `assets.exportCapacityKw` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{month}} {{year}} | de fr-FR hi id-ID it-IT | `portal.levelPay.monthAndYear` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{name}} (portal) | es es-MX id-ID pt-BR | `customers.serviceRequest.event.customerWho` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{name}} +{{count}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `reports.scheduled.sendToMore` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{name}}, version {{version}} | fr-FR | `audit.actor.automation` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{name}}, {{date}} | de es es-MX fr-FR hi id-ID it-IT ko-KR pt-BR | `metering.premises.gis.by` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{number}} · {{amount}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `payments.moveReapply.kicker` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{number}} · {{customer}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `payments.resend.kicker` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{n}} × {{amount}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `customers.account.plan.col.shape` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{pct}}% | hi id-ID ja-JP ko-KR | `reports.dashboard.share` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{percent}}% | hi id-ID it-IT ja-JP ko-KR pt-BR | `portal.billDetail.ratePercent` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{period}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `reports.dashboard.subLine` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{register}} · {{unit}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `metering.quickRead.registerLabel` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{report}} → | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `reports.dashboard.openReport` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{sentence}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `billing.oneTime.err.engineSaid` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{service}} · {{from}} — {{to}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `customers.account.usage.chartRange` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{size}} × {{count}} · base {{base}} | es es-MX pt-BR | `billing.bill.line.sizeBase` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{total}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `integrations.table.apis` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{units}} · {{count}} plan | es es-MX | `rating.rs.wiz.reach_one` | the word that language uses here, spelled the English way (per-language list; the reason is in the gate) |
| {{unit}} · {{premises}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `customers.newAccount.unit.recordTitle` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{what}}: ${{amount}} | es es-MX hi id-ID | `portal.usage.costNamed` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| {{word}} {{on}} | de es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR | `customers.account.plan.outcomeOn` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |
| ~{{pages}} | de es es-MX fr-FR hi id-ID it-IT pt-BR | `billing.print.tile.about` | placeholders joined by a sign — no word (`UNIVERSAL`, or per language where French, German or Japanese write it otherwise) |

_621 values kept._

**Count.** `G15` fresh (`DEF-GOV-9597`): **819 → 669 → 0**, and the gate reads **PASS** (it was red with 791–839 fresh values
through rounds 4–6). Proved red through `run()` after the change (law 7): `ko-KR` `work.approvals.acceptConfirm` planted
as *Accept ✓* → *FAIL: 1 NEW value(s) pasted in English … ko-KR :: work.approvals.acceptConfirm*; restored → PASS.
**The gain is held:** `g15_untranslated_baseline.txt` loses its **1,866** lines that are now translated or judged —
4,803 → 2,937 — so a value pasted back in English fails instead of hiding behind an old line. **What remains is
honest debt, not a zero:** 2,937 baselined values are still the English text (es-MX, hi, id-ID, ja-JP and ko-KR carry
~600 each, mostly `settings.*` and `rating.*` from before 2026-08-31); they were not judged here, because judging them
means translating several thousand sentences into five languages, which is the translation project `DEF-2603` names,
not a word-by-word call.
**Rollback:** redeploy `2.516.2`; no data moves.

### 25.6 · The same misreading one key over — a unit type and the Settings sample (`DEF-MET-9663`, `2.516.4`)

Re-reading the catalogues after 25.4 for the two wrong-sense words still found them: Korean *광고* and Japanese
*コマーシャル* in the Settings sample of unit types, and the unit type *Commercial · master* as Korean *상업 · 석사* — a
master's DEGREE. `DEF-CUS-9662`'s test had looked only at keys ending `.commercial`; it now looks for each wrong-sense
word in every value whose ENGLISH carries the word, and was **red on `f6c0bddaf`** (*"metering.units.type.commercial_master
= コマーシャル・マスター"*, ko-KR and ja-JP failing), green after. Each fix takes the catalogue's own word for a master
meter (the map legend's). Filed `DEF-MET-9663` first.

| Key | Language | Old | New | Why |
|---|---|---|---|---|
| `metering.units.type.commercial_master` | ko-KR | 상업 · 석사 | **상업용 · 마스터 계량기** | *석사* is a master's DEGREE and *광고* an advertisement; the catalogue's master meter is *마스터 계량기*, a commercial unit *상업용* (`DEF-MET-9663`) |
| `settings.reference.sample.unit_types` | ko-KR | 주거용, 주거용 · 서브미터링, 광고, 상업 · 석사, 공용 공간 | **주거용, 주거용 · 서브미터링, 상업용, 상업용 · 마스터 계량기, 공용 공간** | *석사* is a master's DEGREE and *광고* an advertisement; the catalogue's master meter is *마스터 계량기*, a commercial unit *상업용* (`DEF-MET-9663`) |
| `metering.units.type.commercial_master` | ja-JP | コマーシャル・マスター | **商業用・マスターメーター** | *コマーシャル* is a TV commercial; the catalogue's master meter is *マスターメーター*, a commercial unit *商業用* (`DEF-MET-9663`) |
| `settings.reference.sample.unit_types` | ja-JP | 住宅用、住宅用・サブメーター付き、コマーシャル、コマーシャル・マスター、共用エリア | **住宅用、住宅用・サブメーター付き、商業用、商業用・マスターメーター、共用エリア** | *コマーシャル* is a TV commercial; the catalogue's master meter is *マスターメーター*, a commercial unit *商業用* (`DEF-MET-9663`) |
| `metering.units.type.commercial_master` | id-ID | Komersial · master | **Komersial · meter induk** | *master* is English carried over; the catalogue's master meter is *meter induk* (`DEF-MET-9663`) |
| `settings.reference.sample.unit_types` | id-ID | Perumahan, perumahan · sub-meteran, komersial, komersial · master, area umum | **Perumahan, perumahan · sub-meteran, komersial, komersial · meter induk, area umum** | *master* is English carried over; the catalogue's master meter is *meter induk* (`DEF-MET-9663`) |
| `metering.units.type.commercial_master` | pt-BR | Comercial · mestre | **Comercial · medidor mestre** | *mestre* alone is a person (a teacher, a master); the catalogue's word is *medidor mestre* (`DEF-MET-9663`) |
| `settings.reference.sample.unit_types` | pt-BR | Residencial, residencial · submedido, comercial, comercial · mestre, área comum | **Residencial, residencial · submedido, comercial, comercial · medidor mestre, área comum** | *mestre* alone is a person (a teacher, a master); the catalogue's word is *medidor mestre* (`DEF-MET-9663`) |
| `metering.units.type.commercial_master` | it-IT | Commerciale · master | **Commerciale · contatore master** | the unit is commercial with the *contatore master* (the catalogue's map legend word), and *sub-contabilizzato* is not said — *con sottocontatori* is (`DEF-MET-9663`) |
| `metering.units.type.residential_submetered` | it-IT | Residenziale · sub-contabilizzato | **Residenziale · con sottocontatori** | the unit is commercial with the *contatore master* (the catalogue's map legend word), and *sub-contabilizzato* is not said — *con sottocontatori* is (`DEF-MET-9663`) |
| `settings.reference.sample.unit_types` | it-IT | Residenziale, residenziale · sub-contabilizzato, commerciale, commerciale · master, area comune | **Residenziale, residenziale · con sottocontatori, commerciale, commerciale · contatore master, area comune** | the unit is commercial with the *contatore master* (the catalogue's map legend word), and *sub-contabilizzato* is not said — *con sottocontatori* is (`DEF-MET-9663`) |
| `metering.units.type.commercial_master` | hi | वाणिज्यिक · मास्टर | **वाणिज्यिक · मास्टर मीटर** | *मास्टर* alone names nothing; the catalogue's master meter is *मास्टर मीटर* (`DEF-MET-9663`) |
| `settings.reference.sample.unit_types` | hi | आवासीय, आवासीय · सब-मीटर, वाणिज्यिक, वाणिज्यिक · मास्टर, साझा क्षेत्र | **आवासीय, आवासीय · सब-मीटर, वाणिज्यिक, वाणिज्यिक · मास्टर मीटर, साझा क्षेत्र** | *मास्टर* alone names nothing; the catalogue's master meter is *मास्टर मीटर* (`DEF-MET-9663`) |
| `metering.units.type.residential_submetered` | de | Wohnen · untergemessen | **Wohnen · mit Unterzählern** | *untergemessen* is not a German word; a sub-metered home is *mit Unterzählern*, the catalogue's word (`DEF-MET-9663`) |
| `settings.reference.sample.unit_types` | de | Wohnen, Wohnen · untergemessen, Gewerbe, Gewerbe · Hauptzähler, Gemeinschaftsfläche | **Wohnen, Wohnen · mit Unterzählern, Gewerbe, Gewerbe · Hauptzähler, Gemeinschaftsfläche** | *untergemessen* is not a German word; a sub-metered home is *mit Unterzählern*, the catalogue's word (`DEF-MET-9663`) |

**Rollback:** redeploy `2.516.3`; no data moves.

## 26 · Round 6 — lane FIX-6: eleven open defects, red first (`2.516.5`)

One line per fix. Every server fix proved on SQLite and on PostgreSQL 16 (`--ds=config.settings.pgtest`); every screen
fix walked at 1440 on PostgreSQL (`10-scripts/fix6_after_walk.mjs`, 13/13), shots in `08-qa/work-2026-10-04/after/fix6-*.png`.

| Defect | What was wrong → what it does now | Where | Red first |
|---|---|---|---|
| `DEF-WRK-9660` | A rule's job on a device with no service point (backflow, battery, PV, comms) had no premises or unit. `_asset_walk` now follows the device's OPEN assignment to its unit and building (hard rule 8: walked, never stored); a device in the warehouse still stands nowhere. The account is not stamped — read at use from the unit, as P1.15 already does. Walk: *WO-0100 · 401 Quarry Hill Ct* on the rule's Jobs tab | `metering/connections.py` | `test_def_wrk_9660_9661_rule_raise.py` — `assert 'None' == '01a108c4…'` |
| `DEF-WRK-9661` | The Review/Overview promised 4, the sweep raised 3. One check now — `connections._template_asset_refusal`, raised by the raise and ASKED by the preview and the rule's *Tonight* (`metering_seam.raise_refusal`) — so `would_raise` counts only what the sweep raises; `cannot_raise` + reasons are served, the sweep reports `refused`, and both screens add *3 more cannot be raised.* Walk: Review 3 → sweep raised 3, refused 3 | `work/rules.py`, `RuleBuilder.tsx`, `RuleDetailPage.tsx` | same file — `assert 2 == 1`; `cr168Rules.dom.test.tsx` red on the old builder |
| `DEF-MET-9614` | A second run carrying the same file to the same target hit `uq_import_runs_idempotency` at the final save → 500, all rows rolled back. Refused by name before any row: *File already loaded as {{run_no}}.* (`BIZ-IDEMPOTENT`), at the door and in the locked load | `metering/import_runs.py` | `test_def_met_9614_same_file_twice.py` — `IntegrityError: UNIQUE constraint failed` |
| `DEF-WRK-9658` | Raise results (across buildings AND the raise page) link each job number to its order; `orderHref` is REQUIRED so no caller can leave it dead | `raise/RaiseConfirm.tsx` | `cr168Performance.dom.test.tsx` — `expected undefined to be '/brazosbend/work/orders/WO-0042'` |
| `DEF-MET-9649` | *1 units*: the key never existed, a baked default spoke. Plural keys `customers.build.rollup.units_one/_other` and `…raised` in eleven catalogues | `BuildDetailPage.tsx` | `BuildDetailPage.dom.test.tsx` — `not to contain '1 units'` |
| `DEF-CUS-9650` | Opening reads print through `UnitCell` / `formatQuantity` (16,082 kWh, 26.24 kgal) | `MoveRecordPage.tsx` | `MoveRecordPage.test.tsx` — `not to contain '16082.000000'` |
| `DEF-PAY-9644` | Every share, rows and total, prints two places through the new `formatPercentFigure` beside `formatPercent` (BR-SHL-023); the exact sum is unchanged, only the print. Rows moved 33.2 → 33.20 with it (hard rule 2). Walk: *100.00%* | `SummaryTab.tsx`, `PercentCell.tsx` | `SummaryTab.test.tsx` — two red |
| `DEF-SHL-9615` | A server field refusal is shown only while the field still holds the value refused; retype → gone, type it back → back. Schema errors unchanged | `FormModal.tsx` (`useFormCommit`, so `FormPage` too) | `FormModal.dom.test.tsx` — the sentence still present |
| `DEF-WRK-9664` | Certificate row action *Renew* → *Edit* (image 33); the dialog still renews. Filed by this lane (CREWS-2 had it as prose only) | `TechnicianCertificationsTab.tsx` | `crews2Lane.dom.test.tsx` — 2 red |
| `DEF-WRK-9659` | Test restated to the no-drop rule: the bad-task item is HELD; the refused item is now a task ticked before the safety rows (`BIZ-LOCKED`), between good items | `test_us_wrk_044_sync_pg.py` | red on PG per CREWS-2 (`8badcb01c`) |
| `DEF-WRK-9613` | Test restated to the seed: each seeded type's default priority equals `SEED_TYPES`' own (since `91377e779`) | `test_us_wrk_007_010_reference.py` | red on `9f9ec39bf` |
| `DEF-WRK-9657` | NOT REPRODUCED on 2.516.x: the cell has carried `whitespace-nowrap` since `c4346e159`; the coordinator's shot footer reads `v2.513.0` (an older bundle). Measured 20 px per order number at 1440; a class assertion added | — | — |

**Recording:** `work.rule`, `work.rule.jobs`, `work.rule.audit` re-recorded (`cr168_capture_work_shapes.py`, sbh_wfix6) for the new
`tonight` fields; the rule-page tests now read the recording's own name, template and order numbers instead of typing them.
**Filed, not fixed:** `DEF-MET-9665` — `test_DEF_543_FIXED__upsert_UPDATES_a_restated_premises` red on the tip with `import_runs.py`
at HEAD as well. **Reds I did not cause:** G32 (21 unresolved, none of mine), G33 (10 new over cap, none of mine), ruff F401
`customers_seam` in `work/rules.py` (present at `9f9ec39bf`).

**Rollback:** redeploy `2.516.4`. No migration.

## 27 · Round 6 — lane FIX-7: texts reach the customer's phone, and five more (`2.518.0`)

One line per fix. Server fixes proved on SQLite and on PostgreSQL 16 (`--ds=config.settings.pgtest`); every screen fix walked at
1440 on PostgreSQL (`10-scripts/cr168_fix7_walk.mjs`, 6/6), shots in `08-qa/work-2026-10-04/after/fix7-*`. Nine judgments of
ours, none put to the PO — decision-log row of 2026-10-05 *"FIX-7"*.

| Defect | What was wrong → what it does now | Where | Red first |
|---|---|---|---|
| `DEF-NOT-9668` | A work-order text read *Address not looked up* though the customer has a phone. The ONE recipient read now addresses `sms` to the account's primary contact phone (else the customer record's phone), only for a customer who chose texts; no phone → `no_mobile_number`, written and held with its reason; a listed number → held. Millworks' *Visit booked* text → **+1 (402) 555-1049** | `customers/selectors.py` (`_text_recipient`), `SettingsNotificationsTab.tsx` | `test_def_not_9668_text_recipient.py` — 4 red (`assert [(None, 'recipient_not_resolvable', False)] == [('+1 (281) 555-0100', None, False)]`); 24/24 on PG |
| `DEF-NOT-9669` | A text for a customer who never chose texts read as a platform gap; now `no_sms_opt_in` from the read itself, so no writer (the payment receipt queues one per payment) can address it | same | same file — `{'unavailable_reason': 'recipient_not_resolvable'} == {'unavailable_reason': 'no_sms_opt_in'}` |
| `DEF-NOT-9667` | Messages needing attention was 838 px in a 752 px card at 1440 (one 44-character email held its column); the recipient and what-went-wrong cells now break anywhere → 752 in 752 | `notificationsKit.ts` (`BREAK_ANYWHERE_CELL`), `SettingsNotificationsTab.tsx` | `notificationsLayout.dom.test.tsx` — `expected [] to include 'anywhere'` |
| `DEF-WRK-9672` | The crew's day pack had no door; **Print day…** is a printer icon on each crew's row, opening the technician page's own dialog with `crew=<slug>` | `CrewsPage.tsx` | `crewsLane.dom.test.tsx` — `Unable to find … button "Print day…"` |
| `DEF-NOT-9670` | FIELD-2 listed `staff_field_work` (in-app, staff) among the late classes sent AND kept; two `OQ-1164` cases red since `46ded2148`. It is on `NOT_A_DOCUMENT` alone and subtracted by name | `test_oq1164_every_customer_document_freezes.py` | the two cases themselves (42 passed after) |
| `DEF-NOT-5392` (+ duplicates `DEF-NOT-4534`, `DEF-NOT-5120`) | Catalogue said *Statement · email*, seed *· Email* since `3ece617d6` (2026-09-07, `DEF-NOT-4416`); catalogue moved to the agreed *· Email*; one grouping fixture aligned to it | `notifications/catalogs.py`, `templateCatalogGrouping.dom.test.tsx` | `test_def_210…[email_statement/email_past_due/email_payment_receipt]` — red since 2026-09-07 |
| `DEF-NOT-6397` | The preview case asserted the word *Sample*; the PO's ruling of 2026-09-07 (`1c9c3771a`) made the sample *Hi Pat … AC-000000*. The case now asserts that sample | `test_cr_007_template_catalog.py` | red since 2026-09-07 |
| `DEF-WRK-9671` | A certification-rule job on a meter in the warehouse read only a dash for where it is. `stored_at` (the asset's `location_note`, ONLY when the job stands on no premises) reads on Orders, the rule's Jobs, Approvals, a technician's Jobs (`WhereCell`), the order page (*Stored at*) and the printed sheet; no note → dash. **Behaviour unchanged** — whether the rule should raise on a warehouse meter is with the PO | `work/selectors.py`, `work/print_docs.py`, `WhereCell.tsx`, `OrderOverview.tsx` | `test_def_wrk_9671_warehouse_job_location.py` — `KeyError: 'stored_at'`; `WhereCell.dom.test.tsx` |

**Found and reported:** on the sample, the Asset age rule raises WO-0041..43 on AST-04412..14 — meters with no service point,
no assignment and no location note. No surface showed a blank before this change (each read a dash or *Not at an address*).
**Not rewritten:** texts queued before `2.518.0` keep *Address not looked up* (a snapshot, `BR-TEN-017`). **Reds I did not
cause:** `test_cr052_w4_delivery_election` tc8/tc9/tc10/tc13 (a `portal` row on every bill since `5b6aaa823`, 2026-09-07) and
`test_us_cus_017_tc1__confirming_writes_plan_changed_to_audit_log` (`'None' == '2026-08-31'`) — red before this lane.

**Rollback:** redeploy `2.517.0`. No migration. Texts queued under `2.518.0` keep their address.

## 28 · Round 7 — lane WALK-A: the 65 drawings beside the built screens, and the 34 beta observations re-run (`2.518.0` walked · `2.518.4` one fix)

Walked on PostgreSQL 16 at 1440 (`sbh_wwalk`, a fresh `seed_demo` + `load_sample_data`), signed in as Dana. Each drawing was opened as an
image (B14 rule 42) and set beside a photograph of the built screen in the same state; every photograph was opened and checked not blank.
The table, one row per image, is `08-qa/work-2026-10-04/final/WALK-SIDE-BY-SIDE.md`; the photographs are beside it, named as the drawings
are. Judgments of ours: decision-log row *"CR-168 ROUND 7 · WALK-A"*.

### 28.1 · The counts

| | Count | Which |
|---|---|---|
| Images | **65** | 63 photographed; 58 and 60 have no screen by ruling |
| **Matching** | **57** | every image not listed below |
| **Differing** | **6** | 01 (tiles wrap), 02 (no advice line: demo data), 03 (Due blank · no customer number), 04 and 06 (no *Send back…* · no *Complete* chip · no customer number), 22 (no *closed by* — **fixed**) |
| Not built, by ruling | **2** | 58 (Assignment step) and 60 (Escalation step), retired 26 Sep |
| Noted only (rule 44: spacing, type, component) | 2 | 16 (kind words after names, not headings), 30 (segmented Hours) |
| **Defects filed** | **9** | `DEF-WRK-9675` (Send back has no door, high) · `9676` (demo build jobs carry no template — data) · `9677` (Due blank on a no-priority job) · `9678` (Holder without customer number) · `9679` (Accept question without the closer) · `9680` (Orders tiles wrap at 1440) · `9681` (no *Complete* chip) · `9689` (beta #29, Select all not built) · `9690` (beta #28, no Duplicate on an order) |
| **Defects fixed** | **1** | `DEF-WRK-9679` in `2.518.4` — red first (`KeyError: 'closed_by'`; the dialog test *expected … to contain '101 Silver Creek Rd · Water · closed by D. Ortiz'*), green on SQLite and on PostgreSQL 16; photographed as `22b-approvals-accept-closed-by.png` |
| Defects closed as already fixed | 1 | `DEF-WRK-3646` (the Issue log's tooltip-only hold) — the Issue log is live since `2.503.0` (`35-parts-parts.png`) |

**Field added to §7.3 (`GET /work-orders/awaiting-approval`, lane WALK-A, `2.518.4`):** each row carries `closed_by: {name} | null` — the
newest close's author, read for the page in two queries. The recorded fixture `work-orders.awaiting-approval.json` predates it; the type
marks the field optional.

**Performance (65) — At risk is moving by PO ruling** (decision log *"FOUR PO ANSWERS ON WORK"*, 2026-10-05): it becomes its own Work
tab beside Orders; Schedule and Raise across buildings stay inside Performance (lane BOARDS). Photographed as it is on `2.518.0`; not a defect.

### 28.2 · The 34 beta observations (§6), re-run on `2.518.0`

Evidence is a photograph in `final/` (or the walk's printed check, `cr168_r7_observations_walk.mjs` and the group walks).

| # | Reported (short) | Now | Evidence |
|---|---|---|---|
| 1 | Map dots on a blank canvas | **Built; not provable here** — the map asks Esri for 18 street tiles and the CSP allows the host; this sandbox's proxy refuses it (403), so 0 draw. `DEF-WRK-9561` stays open for a deployed check | `24-map-the-day-on-the-ground.png` (*Tiles © Esri*) |
| 2 | *+ New work order* at the bottom | **Fixed** — top right | `01` |
| 3 | Two clear crosses in the search box | **Still true** — the kit's ✕ beside Chromium's own on the Orders search (`DEF-SHL-5345`, open) | `obs03-orders-search-two-crosses.png` — the walk's check prints `nativeShown: true, kit: 1` |
| 4 | Edit / assign fails silently | **Fixed** — a crew, a contractor and a person each save (HTTP 200) | `12`, `13`; assign walk |
| 5 | Rules unclear | **Fixed** — *+ New rule*, row actions, a rule's own page | `56`, `62` |
| 6 | Builder tasks not editable | **Fixed** | `50` |
| 7 | Builder materials etc. not editable | **Fixed** | `49`, `51`, `52` |
| 8 | Help document has no upload | **Fixed** — upload, link, video badge | `53` |
| 9 | Versions *What changed* blank | **Fixed** | `46` |
| 10 | An approved order gets lost | **Fixed** — WO-0037 is a row on Orders under *Status · Complete*, and its page offers *Print* only | `obs10-accepted-order-on-orders.png`, `obs10-accepted-order-page.png` |
| 11 | Reschedule takes garbage | **Fixed** — a date picker and a window list | `obs11-reschedule-date-and-window.png` |
| 12 | *Filter not working* | **Fixed** — 30 of 32 open orders carry a priority | walk check #12 |
| 13 | Duplicate gives a Draft | Correct by design (unchanged) | — |
| 14 | Create WO fields should be dropdowns | **Fixed** | `14`, `15` |
| 15 | Rules search not working | **Fixed** — *Leak* leaves one row | rules walk 56b |
| 16 | Raise from address + sub-area | **Built** (raise on units) | `14` |
| 17 | *Register buttons* use case | **Fixed** — the Issue log is live (`DEF-WRK-3646` closed with it) | `35` |
| 18 | Approvals 👁 opens the premises | **Fixed** — every eye opens `/work/orders/<id>` | orders walk EYE HREFS |
| 19 | A map pin should open the order | **Fixed** — all 24 orders reached on their own page, by mouse and keyboard | map walk |
| 20 | No service / purpose on a template | **Fixed** — *Done to* asked and listed | `43`, `48` |
| 21 | Assign while creating | **Built** | `16` |
| 22 | Raise from the account | **Fixed** — arrives filled | `19` |
| 23 | Raise from the asset | **Built** (ruling 35) | `20` |
| 24 | No edit part | **Fixed** | parts walk `36c` |
| 25 | No active / inactive part | **Fixed** | parts walk `35b`, `35c` |
| 26 | No filters on parts | **Fixed** | `35` (+ Filter); parts walk `35d` |
| 27 | Photos / readings only on the checklist | **Built** — photographs, values, the viewer | `06`, `09` |
| 28 | Duplicate on orders and rules | **Half** — on a rule: built (`62`); on an order: **still absent**, filed `DEF-WRK-9690` | walk check #28 |
| 29 | Select all | **Still true** — filed `DEF-WRK-9689` (P3.6 was never given to a lane) | walk check #29 |
| 30 | Consumer info missing | **Fixed** — Account, Holder, Phone | `03` |
| 31 | Asset / unit not shown | **Fixed** — Meter and Unit on the head and Overview | `03` |
| 32 | Type and sub-type one list | **Still true** — *Electrical Line, Outage report, Transformer fault…* sit at one indent in the Orders filter (`DEF-WRK-9582`, open) | `obs32-orders-type-filter-flat.png`; walk check #32 |
| 33 | Invited technician cannot sign in | **Fixed** in `2.493.2` (`DEF-WRK-9583`); a technician closes jobs through the technician API in WALK-B's flows | WALK-B `a4a1963e4` |
| 34 | Raise form fields | **Built** (P2.2) | `14`, `16` |

**Count (34):** **fixed 23** (#2, 4–12, 14, 15, 17–20, 22, 24–26, 30, 31, 33) · **built as a change 5** (#16, 21, 23, 27, 34) · **correct by design 1** (#13) · **half 1** (#28) · **still true 3** (#3, 29, 32) · **built, not provable here 1** (#1). 23 + 5 + 1 + 1 + 3 + 1 = 34.

### 28.3 · Reds I did not cause, and what the walks needed

- `cr168_assign_walk.mjs` is red on 2 of 10 checks on a fresh seed — M. Chen is not told *Missing skill* and the bulk line is empty —
  because the sample builds' jobs carry no template (`DEF-WRK-9676`, data). The advice code is right; it is given nothing to say.
- `cr168_orders_list_after_walk.mjs` failed at image 12 on `2.518.0`: *Assigned to* has been a typeable picker since `2.499.0`, not a
  `<select>`. It now takes `SKIP_ASSIGN=1` and leaves 12/13 to the assign walk.
- `cr168_orders_list_walk_prep.py` was refused by the photo guard (P1.33, `work.order.photos_still_needed`); it now photographs required rows
  first, as the technician would.
- `cr168_crews_after_walk.mjs` and `cr168_crews2_walk.mjs` stop at a *Renew* button that CREWS-2 replaced with ✎ Edit (image 33 draws the
  pencil); image 34 is taken by the observations walk instead. Not filed: a walk script, not the product.

**Rollback:** redeploy `2.518.3`. No migration. The Approvals row loses `closed_by` and the question its last clause.

## 29 · Round 7 — lane WALK-B: every flow that raises work, walked end to end, and the technician-app rulings proved again (`2.518.0` walked · `2.518.1`–`2.518.3` three fixes)

**The PO's questions:** *"are you also raising work orders from Move In, New Connect, Move out etc - and then when work orders are completed
is clerk able to see the status update in those requests"* and *"use those apis with payload to complete the jobs"*.

**How.** PostgreSQL 16 `sbh_wwalkb` (migrate + `seed_demo` + `load_sample_data --tenant brazosbend`), API on :8087, the built SPA on :5219.
Each job was **raised in the browser as Dana at 1440** through the flow's own door, **closed by R. Patel through the technician API**
(`10-scripts/technician_api_walk.py --no-accept`, every request and answer captured in `api-w*.json`), **accepted by Dana in the browser**,
and the originating record photographed after. The office never completed a job (ruling 18). Photographs and captures:
`08-qa/work-2026-10-04/final/flows/` (W1–W17) and `…/flows/rulings/`; every photograph cited here was opened.
Judgments: decision log *"CR-168 ROUND 7 · WALK-B — FIVE JUDGMENTS"*.

| # | Source | Raised (door → job) | Closed by Patel (API) | Accepted (Dana, browser) | Status back on the clerk's record | Result | Evidence |
|---|---|---|---|---|---|---|---|
| W1 | `new_connect` | CON-26-0126 (*Waiting on: inspection*) WO-0033/34; and a new build CON-26-0129 committed in the New Connect wizard → WO-0045/46/47 | all five, 44 items, 8 photos | 33, 34, 45, 46 accepted; **47 (Meter set) refused for ever** | CON-26-0126: *5 of 5*, *Waiting on* gone, *Approve* in the head. CON-26-0129: *3 of 3* but WO-0047 unacceptable | **PASS** on the seeded build · **FAIL** on a fresh build → `DEF-WRK-9683` (filed). The refusal had read *Could not accept.* → `DEF-WRK-9682` **fixed `2.518.2`** (*This job names no meter.*) | `w01-con0126-before/after.png`, `w01-con0129-after.png`, `w01-def-wrk-9682-accept-says-why.png`, `api-w01-new-connect.json` |
| W2 | `move_out` | AC-2026-00002 move-out wizard, *+ Add work order* Re-read → MVO-26-0002 → WO-0041 | close only (the row raises the job TYPE: no template, no checklist) | yes | *Visit 1 raised · 1 done · 1 accepted WO-0041* | **PASS** (note: a clerk-added visit row carries no template, so the phone has nothing to tick or read) | `w02-move-out-record-before/after.png` |
| W3 | `move_in` | the vacated unit, move-in wizard (Rosa Delgado, texts on) → MVI-26-0004 → WO-0042 | yes | yes | *Visit 1 raised · 1 done · 1 accepted WO-0042*, never *Not raised* | **PASS** | `w03-move-in-record-before/after.png`, `api-w03-WO-0042.json` |
| W4 | `transfer` | AC-2026-00003 sold to Marcus Lee → TRF-26-0001 → WO-0043 | yes | yes | *Changeover read 1 raised · 1 done* | **PASS** | `w04-transfer-record-before/after.png`, `api-w04-WO-0043.json` |
| W5 | `reconnect` | DSC-26-0002 water cut in the wizard and marked cut; reconnect row → WO-0044 | yes | yes | after reload: *WO-0044 R. Patel · Accepted*, *1 raised · 0 to raise* | **PASS** · on DSC-26-0001 (electric, no reconnect template) the row's raise said nothing and stuck → `DEF-CUS-9674` **fixed `2.518.1`** | `w05-reconnect-page-before/after.png`, `w05-def-cus-9674-refusal-shown.png` |
| W6 | `service_request` | new request SR-26-0009 (16 Poplar Grove, vacant) → *Approve · Move-in* → child move-in → WO-0049 | yes | yes | the request links to **MVI-26-0005**, which reads *Approved · Visit: Not raised*; the visit is on **MVI-26-0006** (*1 raised · 1 done · 1 accepted*) | **FAIL** → `DEF-CUS-9684` (filed): one move-in, two numbers | `w06-request-after.png`, `w06-request-child-link-opens.png`, `w06-the-real-move-record-after.png` |
| W7 | `meter_read` | CY-001 › Still to read › W-7001 › *Send someone out* → WO-0050 | yes | yes | *Raised by Meter read*; on the meter the done job is **nowhere** | **PASS** after fix: the modal offered no template at all → `DEF-MET-9685` **fixed `2.518.3`** · **FAIL** on the meter's page → `DEF-AST-9686` (filed) | `w07-send-someone-out-offer.png`, `w07-send-someone-out-raised.png`, `w07-meter-w7001-work-tab-after.png` |
| W8 | `failed_outcome` | dispatcher WO-0052 | closed **Failed** | yes | WO-0053 *Raised by Failed job*, *Follows WO-0052*; WO-0052 *Follow-up WO-0053* | **PASS** | `w08-wo0052-failed-accepted.png`, `w08-wo0053-follow-up.png` |
| W9 | `dispatcher` | raise wizard on 107 Mill Pond Ln → WO-0051 | 12 items | yes | premises › Work orders › *All*: WO-0051 *Completed* | **PASS** · the booked window is stored five hours early → `DEF-WRK-9688` (filed) | `w09-premises-work-orders-all-after.png` |
| W10 | `assets` | W-5005 › *Raise work order* → WO-0054 | 12 items | yes | meter's tab: *No open jobs*; History is the maintenance log only | **FAIL** → `DEF-AST-9686` (filed) | `w10-asset-work-tab-before/after.png` |
| W11 | `asset_age_rule` | the sweep, by hand → WO-0055/56/57 on warehouse meters | WO-0056 | refused *This job names several meters.* | *Raised by Asset age rule* | **PASS** for the raise. A job on a warehouse meter is **changing by PO ruling** (decision log *FOUR PO ANSWERS ON WORK*, lane BOARDS). The refused Accept is `OQ-WRK-1723` / `DEF-WRK-9654`, both open | `w11-wo0055-raised-by-asset-age-rule.png`, `w11-wo0056-accept.png` |
| W12 | `dunning_auto` | the disconnect wizard's *Work order* row on DSC-26-0001 and DSC-26-0002: *1 work orders will be raised*, **0 raised**, twice | — | — | the case shows no visit | **FAIL** → `DEF-CUS-9631` (open, re-measured) · the rule half is **not reachable before 14 Oct** on this demo (earliest final notice 12 Oct) | `w12-disconnect-wizard-confirm.png`, `w12-disconnect-case-after-schedule.png` |
| W13 | `high_usage_alert` | *Leak investigation* turned on in Work › Rules; the sweep raised **46** jobs (WO-0058..0103) | WO-0058 | refused *several meters* (the rule's template is the meter exchange) | *Raised by High-usage alert* | **PASS** for the raise (Accept: `OQ-WRK-1723`) | `w13-w15-rules-turned-on.png`, `w13-wo0058-raised-by-leak-rule.png` |
| W14 | `billing_exception` | no unresolved bill-run break on the demo; CY-001's September run stops at *0 ready* (discarded) | — | — | — | **NOT REACHABLE today** (judgment 1) | `w14-bill-run-check.png` |
| W15 | `compliance_calendar` | *Backflow test due* turned on; BF-0901 added (due 20 Oct); the sweep found it and **refused** `asset_type_not_on_template` | — | — | — | **FAIL** → `DEF-WRK-9687` (filed): the seeded rule raises a meter template on a backflow preventer | sweep output in the commit message |
| W16 | `payment_received` | a $8,315.00 card payment on cut account A-11340 (PY-261004-0085) | — | — | work orders **103 before, 103 after** | **PASS** (raises nothing, `BR-PAY-036`). The receipt panel still prints raw `payments.problem.*` keys — `DEF-268`, open | `w16-payment-recorded.png` |
| W17 | the phone | WO-0104 (3 photo-required tasks), R. Patel in the field app at **390 × 844**: safety, tasks, a photo on each task row, two readings, *Passed*, *Location within 8 m* | on the phone alone: completed, 3 links landed | yes, at 1440 | *Completed · Passed · Accepted*, no *Location not precise* | **PASS**; and sync **refuses** a close with a required photo missing (`work.order.photos_still_needed`, not acknowledged, order stays *Planned* — WO-0108) | `w17-03…07-*-390.png`, `w17-08-dana-accepted-1440.png`, `rulings/proofs.txt` |

**The technician-app rulings, proved again on `2.518.3`** (`10-scripts/cr168_r7_walkb_prep.py` raises the jobs through the services;
`technician_api_walk.py` and `10-scripts/cr168_r7_walkb_tech_proofs.py` drive the API):

| Ruling | Proof | Result | Evidence |
|---|---|---|---|
| Shared tablet | WO-0110: Patel captured 6 items offline and signed out; Chen signed in — his feed WO-0025, WO-0111, none of Patel's; Patel's job → **404**; the device sent Patel's work under Chen's session | **PASS**: all 6 receipts *captured as r.patel* | `rulings/shared-tablet-WO-0110.txt`, `…-receipts.txt` |
| Location | WO-0106 closed with a **300 m** fix | **PASS**: office *precise: false*; the order reads *Location not precise* | `rulings/fix-300m-WO-0106-location-not-precise.png` |
| Replay | WO-0107, every page sent twice | **PASS**: replay *0 accepted · 5 duplicate*, *0 · 1*; 6 receipts for 6 keys | `rulings/replay-WO-0107.txt`, `…-receipts.txt` |
| Never reject a photo | WO-0108, a **4,082,031-byte** photo (over the 2 MB asked) PUT to its link | **PASS**: 200 *landed*, stored **97,510 bytes**, audited | `rulings/photo-2mb-stored.txt` |
| Accept held while photos upload | WO-0108 closed with the photo declared, bytes not sent | **PASS**: Accept **409** `work.order.photos_uploading` (count 1), **200** after it landed | `rulings/proofs.txt` |
| Reassigned while offline | WO-0109: Patel captured 3 items offline; office reassigned to M. Chen; the device synced | **PASS**: 3/3 `held_for_review` `work.mobile.not_your_job`, all acknowledged | `rulings/proofs.txt` |
| Same-day readings | WO-0105 on E-5000 (office 3,400 kWh on 5 Oct), Patel reads **3,412**, Dana accepts | **PASS**: both kept; `counted_among` → **3,412**; the meter's Reads tab: 3,412 *Counts for billing*, 3,400 *Kept as history* | `rulings/same-day-E-5000-reads-tab.png`, `…-counted.txt` |
| Texts (`DEF-NOT-9668`) | Rosa Delgado chose texts at move-in; WO-0042 assigned and set off | **PASS**: `sms_visit_booked` and `sms_technician_on_the_way` queued **to +1 512 555 0142**; customers who did not choose texts get none | `rulings/sms-visit-texts.txt` |

**The 1,000-record proof** (`technician_api_load.py`, WO-0112, PostgreSQL 16, 4 lanes sharing 4 CPUs):

| Leg | Wall clock |
|---|---|
| down: 1,000 readings, paged | 0.2 s |
| up: 2,000 records in 10 pages (no image) | 42.4 s |
| replay: page 1 again (200/200 duplicate, same links) | 0.9 s |
| images: first 400, then the connection drops | 72.0 s |
| images: resume the remaining 600 (+10 deliberate re-sends, 5 hash mismatches re-sent) | 188.4 s |
| close + accept | 1.1 s (Accept 200) |

Moved: 0.24 MB down, 1.77 MB of records up, 135.50 MB of images. **Database after: 2,001 receipts for 2,001 keys, 1,000 links all landed,
1,000 attachments on 1,000 distinct documents, largest stored photo 102,355 bytes (50 received over 100 KB and shrunk), 0 links still
holding staged bytes — 0 dropped, 0 duplicated.** No request near the 60-second worker limit (a page of 200 took about 4 s).

**Defects.** Filed and fixed red-first: `DEF-CUS-9674` (`2.518.1`), `DEF-WRK-9682` (`2.518.2`), `DEF-MET-9685` (`2.518.3`). Filed, open:
`DEF-WRK-9683`, `DEF-CUS-9684`, `DEF-AST-9686`, `DEF-WRK-9687`, `DEF-WRK-9688`, `DEF-AST-9691` (the Reads tab counts the same-day pair as one row: *1–4 of 4* under five). Re-measured open: `DEF-CUS-9631`, `DEF-268`,
`OQ-WRK-1723` / `DEF-WRK-9654`.

**Reds I did not cause.** No suite was red in the files this lane touched (19/19 reconnect, 58/58 order page, 11/11 Reads field work).

**Rollback:** redeploy `2.518.0` (three front-end fixes, no migration). The walk's data is on `sbh_wwalkb` only.

## 30 · Round 7 — lane BOARDS: the PO's four answers on Work (`2.519.0`)

The rulings, decision log 2026-10-05 *"FOUR PO ANSWERS ON WORK"*, verbatim:

1. *"(b) Make At risk its own tab next to Orders, because the design says "a dispatcher opens it first". Schedule and Raise across buildings stay inside Performance."*
2. *"(b) Add a daily limit per technician (default 6), editable on the technician's page."*
3. *"(b) Only raise jobs for meters that are installed."*
4. *"(a) Keep it: text the phone on file, but only for customers who chose texts."*

Our six judgments: decision log *"CR-168 §30 · BOARDS"*. Rules: `BR-WRK-064`, `BR-WRK-065`, `BR-WRK-066`, `BR-NOT-1040`.

| Answer | What a user gets | Where |
|---|---|---|
| (1) | **At risk** is a Work tab right after Orders, at `/work/at-risk`, badge `WRK-25` (minted). The board is unchanged (same read, paged on the server). The old address `/work/performance?view=at-risk` opens the tab. Performance keeps *Results · Schedule · Raise across buildings* | `AtRiskPage.tsx` (new), `WorkShell.tsx`, `PerformancePage.tsx`, `App.tsx`, `screenIds.ts`, `g29_allocated_badges.txt` |
| (2) | Every technician has a **daily job limit**, 6 to start with (`work/0038`), shown on their Overview with *Edit*, saved by `PATCH /work/technicians/{slug} {daily_job_limit}` (a whole number of 1 or more, no upper bound, audited). The candidates read adds `advice.daily_job_limit` and `advice.over_daily_limit` (still paged). The Schedule board reads **Over limit of 6** in red beside *Off, has jobs*; the assign advice says *Over daily limit of 6*. Advice only — the seventh job is still given | `models.py`, `workforce.py`, `api.py`, `advice.py`; `TechnicianDailyLimit.tsx` (new), `TechnicianDetailPage.tsx`, `ScheduleBoard.tsx`, `candidateAdvice.ts`, `workEndpoints.ts` |
| (3) | *An asset passes its certification* and *… is due soon* find only an asset on a service point or an open assignment. The preview, *Tonight* and the sweep count the same meters. Nothing already raised is touched | `work/seams/assets_seam.py` (`_installed_q`) |
| (4) | No change — `2.518.0` already texts the phone on file only for customers who chose texts. Written down as `BR-NOT-1040`, superseding `DEF-2700`'s rule of 2026-08-31 for those customers | `04-docs/05-modules/10-notifications/02-business-rules.md` |

**Proof.** Red first on `07232b574`: `tests/test_cr168_boards_lane.py` — 12 failed, 1 error (*'Technician' object has no attribute 'daily_job_limit'*, *assert 200 == 422*, *assert (2, 2, 0) == (1, 1, 0)*, *assert 'M-30E' not in ['M-30E']*); vitest `WorkShell.test.tsx` (*expected [ 'orders', 'approvals', … ] to deeply equal [ 'orders', 'at-risk', … ]*), `TechnicianDailyLimit.dom.test.tsx` (*Unable to find … work.technician.dailyLimit.value*), `cr168Performance.dom.test.tsx` (*Failed to resolve import "../AtRiskPage"*). After: the 15 server cases green on SQLite and on PostgreSQL 16 (`--ds=config.settings.pgtest`); 91 of 92 rule, assign and escalation cases on SQLite (the 92nd is `DEF-WRK-9695`, below); vitest work + routing + i18n + styles 853 passed; `tsc` clean; G7, G15, G29, G31, G43 pass. `work/0038` up → down → up on PostgreSQL 16. **Seven rule tests** whose subject was a meter on the shelf now install it (`make_installed_asset`), because answer (3) makes the shelf meter no subject at all.

**Walked at 1440 on PostgreSQL** (`sbh_wboards`; `10-scripts/cr168_boards_walk_prep.py` then `DAY=2026-10-06 node 10-scripts/cr168_boards_walk.mjs`): Work tabs `orders, at-risk, approvals, map, crews, parts, templates, rules, performance`; At risk 18 rows, *Within 72 h or late: 18*; the old address lands on `/brazosbend/work/at-risk`; D. Ortiz's limit 7 → typed 6 → *6 jobs a day*, server `6`; on 6 Oct D. Ortiz holds 7 jobs and reads *Over limit of 6* (`data-holder-load="limit"`); the Asset age rule's sweep raised **one** job, WO-0042 on the installed `AST-04413` at 1408 Bluestem Ln, and **none** on `AST-04412` / `AST-04414` on the shelf; *Tonight it raises 0 jobs*.

**Photographs** (`08-qa/work-2026-10-04/after/`, each opened, none blank): `boards-1-at-risk-tab.png`, `boards-2-performance-views.png`, `boards-3-limit-form.png`, `boards-4-limit-saved.png`, `boards-5-schedule-over-limit.png`, `boards-6-rule-overview.png`, `boards-7-rule-jobs.png`.

**On the demo, stated:** the three sample aged meters are seeded in inventory on purpose (`core/sample_fixture.py`), so on a fresh demo the *Asset age rule* now finds 0 where it found 3; the walk installs `AST-04413` to show both halves.

**Filed:** `DEF-WRK-9695` — `test_p359` is red between midnight UTC and midnight in the utility's zone (a test clock, not this change). **Reds I did not cause:** `test_us_wrk_037_rules_pg.py::test_m6_…` asserts no rule is visible from Lone Star Ridge, which a superuser connection cannot show (RLS bypassed — the `core.W001` warning); G13 (`RateScheduleWizard`, `moveReadsCapture`), G32 (21 payments keys) and G33 (10 new over-length refusals, none of them Work's) were red before this lane.

**Rollback:** `migrate work 0037`, then redeploy `2.518.4`. The column is dropped and every changed limit is lost; the boards fall back to *Off, has jobs* alone.

## 31 · Round 8 — lane FIX-8A: the walk's defects, red first (`2.519.1` …)

From §28 and §29. Each row was read in the register first, filed tests went red before the fix, and each is closed with
`close_defect.py`. Judgments: decision log *"CR-168 ROUND 8 · FIX-8A"*.

| Defect | What a person saw | What was wrong | Fix | Red → green | Build |
|---|---|---|---|---|---|
| `DEF-WRK-9688` (high) | A Brazos Bend visit booked 08:00–12:00 read 03:00–07:00 on the order, the phone and the customer's text | `parse_moment` read a typed (naive) time in the SERVER's zone (UTC); the edit form read stored instants in the BROWSER's zone; the history line and the *Due today* tile used UTC | A naive time is read in the utility's zone (`tenant_settings.timezone`); the edit form opens on the server's `appointment` (utility's clock); the phone card carries `appointment`; the history label, the message's completed date and *Due today* use the utility's day | `test_def_wrk_9688_utility_time.py` (5): *stored 08:00Z, expected 13:00Z*; *'03:00' != '08:00'* → 5 passed · `OrderEditPage.test.tsx`: *expected { due_at: '2026-10-06T00:00:00', … } to deeply equal {}* → 9 passed · `TodayPage.dom.test.tsx`: *expected … to contain '08:00–12:00'* → 14 passed | `2.519.1` |
| `DEF-WRK-9693` (medium) | A job given out with no visit booked was never on the technician's Today or Week | The day kept an unbooked job only when its DEADLINE fell inside the day | Every unbooked open job is on the day, last, flagged `unscheduled`; the phone draws it under *Unscheduled* (11 catalogues) | `test_def_wrk_9693_unscheduled.py`: *['WO-0001'] == ['WO-0001', 'WO-0002']* → passed · `TodayPage.dom.test.tsx`: *Unable to find … unscheduled-heading* → passed | `2.519.1` |
| `DEF-WRK-9683` (high) | CON-26-0129's *Meter set* (WO-0047) closed with both readings; Accept answered *This job names no meter.* every time | The build commit created the meter (in inventory) and raised the job without naming it; `DEF-WRK-9620`'s fallback finds only in-service meters | The commit hands a *per asset* job the ONE meter it fits for that service (unit-narrowed); two are left alone (`OQ-WRK-1723`). The sample *Meter set* stops posting the text *Meter number as fitted* | `test_def_wrk_9683_build_meter_set.py`: *the build's meter-set job names no meter*; `BizError: BIZ-STATE (work.reading.no_meter_on_order)` → 3 passed | `2.520.1` |
| `DEF-CUS-9684` (high) | SR-26-0009 linked to MVI-26-0005 (*Visit: Not raised*); the move and WO-0049 were on MVI-26-0006 | `record_move` took the wizard draft's freshly minted number over the approval's | Job → draft → mint: the approval's number wins | `test_def_cus_9684_one_move_in_one_number.py`: *the request names MVI-26-0001, the move was filed as MVI-26-0002* → passed (and `test_br_cus_1090_*` 13 passed) | `2.520.1` |
| `DEF-AST-9686` (medium) | WO-0050 and WO-0054 left the meter's page once done | The tab drew open jobs only; History was the maintenance log | History opens with **Finished work** — the same fetched rows, not open, with *Accepted*, the completion date and who; a count line when the meter has more than one page | `AssetDetail.test.tsx`: *expected -1 to be greater than -1* (no *Finished work*) → 55 passed | `2.520.1` |
| `DEF-AST-9691` (low) | E-5000's Reads: five rows over *1–4 of 4* | The page is read DATES (two readings kept on one day are two rows), the footer said rows | The footer says *Read dates 1–4 of 4* and *Dates per page* (`ListPager` takes the two keys) | `AssetDetail.test.tsx`: *expected … to contain 'Read dates 1–2 of 2'* → passed | `2.520.1` |
| `DEF-WRK-9687` (medium) | *Backflow test due* found BF-0901 and raised nothing, refused `asset_type_not_on_template`, every night | The seed pointed all seven rules at the meter-exchange template, done to meters only | A seeded *Backflow test* template (water, per asset, *Backflow preventer* only) for that one rule | `test_def_wrk_9687_backflow_rule_template.py`: *'work.order.asset_type_not_on_template' is None* → passed; `test_cr070_m_sample_data.py` amended (six rules share the exchange template, the seventh does not) | `2.520.2` |
| `DEF-CUS-9631` (high) | *1 work orders will be raised*, 0 raised (DSC-26-0001/0002) | The plan never carried step 3's rows and the server had no door for a cut visit | `visits: [{service, instruction}]` on `POST /disconnects/schedule`; Work's seventh flow door `disconnect` raises one job per row (`metering/0075` widens `ck_work_orders_source`); the row reads *Raised when you schedule* (the dead *+ Raise work order* and its two keys retired) | `test_def_cus_9631_disconnect_wizard_visits.py`: *assert 0 == 1*, then *CHECK constraint failed: ck_work_orders_source* → passed · `DisconnectWizard.test.tsx`: *expected undefined to deeply equal [ { service: 'water', … } ]* → 64 passed | `2.520.2` |
| `DEF-CUS-9692` (low) | TRF-26-0001: *Committed by: Not recorded* | `transfers` kept when, not who | `transfers.committed_by` (`customers/0079`), written at commit and read with the time | `test_def_cus_9692_transfer_committer.py`: *committed_by_not_stored … is None*; *no field named 'committed_by_id'* → 2 passed; `test_def_cus_6429_*` amended | `2.520.2` |

**Existing rows (`DEF-WRK-9688`).** Not migrated, and the reason is a fact about the data rather than caution: a window written by a
screen (shifted) and one written by a flow, the technician API or the sample data (correct) look the same in the row. A window booked from a
screen before `2.519.1` reads early by the utility's UTC offset — 5 hours on US Central in summer, 6 in winter — and is re-booked once.

**Reds I did not cause** (dated): `test_us_wrk_024_027_dispatch.py` — `tc3_due_at_is_the_raise_plus_the_priority_sla`,
`tc7_the_list_sorts_by_priority_rank_then_due_time` and `tc4_each_of_the_five_chips_narrows_the_list` (a raised order carries no priority) are
red on `479a4180c` with this lane's five backend files restored to that commit's bytes — measured, not assumed.
Also red on `cc0994207` with this lane's batch-2 files restored to that commit's bytes: `test_us_wrk_039_from_flows.py` (`tc4_…closes_on_the_third_acceptance`,
`tc9_the_source_vocabulary_is_fourteen…`, `def_wrk_3725_the_move_out_field_visit_is_on_step_2…`), `test_br_cus_030_close_reason.py::test_item3_…`
(`customers.account.close_reason_unknown` is in no catalogue) and `test_def_cus_6135_…` ×2 (`park_row() missing … 'today' and 'zone'`).

**Filed by this lane:** `DEF-CUS-9696` — the disconnect case page does not list the cut visit it now raises (the job is on Work › Orders,
*Raised by: Disconnection*, and on the account; the case record has no work-order read).

**`DEF-WRK-9688` proved on PostgreSQL 16** (`sbh_wfix8a`: `seed_demo` + `load_sample_data --tenant brazosbend`, migrated to `2.520.2`; API
`runserver :8091`, the built SPA on `:5223`; both browsers deliberately in **UTC**, the zone every earlier walk read in). Dana booked WO-0016
for R. Patel on 6 Oct, Morning, with the edit page's own patch (`10-scripts/cr168_r8_fix8a_walk.mjs`, 9 PASS / 0 FAIL):

| Surface | Reads |
|---|---|
| Stored | `2026-10-06T13:00:00+00:00` – `17:00:00+00:00` (Central 08:00–12:00) |
| The edit page, reopened | *10/06/2026 · 08:00–12:00*; *Customer — not told; visit unchanged* (no phantom move) — `fix8a-01-edit-reopens-morning-utc-browser.png` |
| The order page | *10/06/2026 08:00–12:00* — `fix8a-02-order-page-0800-1200.png` |
| R. Patel's Week (field app) | WO-0016 *08:00–12:00*; WO-0038 under **Unscheduled** (`DEF-WRK-9693`) — `fix8a-03-technician-week-0800-1200.png` |
| The customer's text (render context), the history line, the printed sheet | *Tuesday, October 6, 2026 · 08:00–12:00*; *08:00–12:00*; *Tue Oct 6, 2026 · 08:00–12:00* — `fix8a-def-wrk-9688-pg-report.txt` (`10-scripts/cr168_r8_fix8a_walk_prep.py report`) |

The four fixes of `2.520.1`/`2.520.2` were proved on PostgreSQL 16 by their tests (`--ds=config.settings.pgtest`: 8 passed) rather than walked.

**Not done here:** `OQ-WRK-1723` / `DEF-WRK-9654` untouched (two meters on one job are still not guessed between). `DEF-CUS-9696` (the case page
lists no cut visit) is filed and open.

**Rollback:** redeploy `2.519.0` for all of §31; reverse `customers/0079` (the committers recorded since are lost) and, after re-sourcing any
`disconnect` job, `metering/0075`.

## 32 · Round 8 — lane FIX-8B: §28's differing drawings and three beta observations, red first (`2.520.0`)

Walked on PostgreSQL 16 at 1440 (`sbh_wfix8b`, a fresh `seed_demo` + `load_sample_data` on this commit's seed, then
`10-scripts/cr168_r8_fix8b_walk_prep.py`), signed in as Dana; the drawings (images 01, 03, 04, 06) were opened as images (B14 rule 42).
`10-scripts/cr168_r8_fix8b_walk.mjs` prints **14 PASS, 0 FAIL**. Photographs: `08-qa/work-2026-10-04/final/fix8b-01…12-*.png`, each opened
and checked not blank. Judgments of ours: decision-log row *"CR-168 ROUND 8 · FIX-8B"*.

| Defect | What a person sees now | Red first (on the tip, before the fix) | Photograph |
|---|---|---|---|
| `DEF-WRK-9675` (high) | A finished job not yet accepted: *Print · Duplicate · Send back… · Accept ✓*. *Send back…* asks a required *Reason* and one consequence line, posts `/send-back`; the job returns to *In progress · Scheduled* and the Audit tab reads *Sent back* with the reason. An accepted job offers no Send back. | `expected [ 'Print', 'Accept ✓' ] to deeply equal [ 'Print', 'Duplicate', …(2) ]` | `fix8b-05`, `-06`, `-07` |
| `DEF-WRK-9681` | The head reads *Complete · Completed · Passed · Awaiting approval*, as image 04 draws it; a finished job still carrying a stale dispatch status reads *Complete*. **Reverses `DEF-WRK-9643`** (judgment 1). | `expected [ 'Completed', 'Passed', 'Accepted' ] to deeply equal [ 'Complete', 'Completed', …(2) ]` | `fix8b-05` |
| `DEF-WRK-9677` | *Due* on a job raised with no priority reads the date it is measured against (`sla.due_at`, raise + the default target): *10/08/2026 00:07* on WO-0043. | `expected '—' to contain '09/27/2026'` | `fix8b-08` |
| `DEF-WRK-9678` | *Holder · Ana Alvarez · C-00001* (images 03/04). The order's `customer` carries `customer_no`, read through `customers.selectors.customer_nos_for` (the first link, as S17's CUSTOMER # column). | `KeyError: 'customer_no'` | `fix8b-05` |
| `DEF-WRK-9690` | *Duplicate* on every shape of an order: confirm *"A new unassigned job is raised."*, then the new order opens (WO-0043 → WO-0045). `POST /work-orders/{id}/duplicate` (`apps/work/duplicate.py`). | `module 'apps.work.api' has no attribute 'work_order_duplicate'` | `fix8b-09`, `-10` |
| `DEF-WRK-9689` (P3.6) | A *Select all* box heads the Select column and ticks the page (19 of 19); when more orders match than the page shows, the bar offers *Choose all N*, which reads every matching order page by page (500 a page) and says *All N orders chosen.* The demo has 19 open orders, under one page, so *Choose all* is proved in the dom suite, not in the photograph. | `no Select all box in the select column's head: expected null not to be null` | `fix8b-02` |
| `DEF-WRK-9680` | Five tiles on ONE row at 1440 (grid 1,152 px); at 900 they wrap to 3 rows. `KPIStrip` gained `tiles="count"` (a 224 px / `14rem` track, on the scale); every other strip keeps 240 px. | `expected null to be 'count'` | `fix8b-01` |
| `DEF-SHL-5345` | One ✕ in every list's search box: the kit's input hides Chromium's own cancel button with a Tailwind utility (no stylesheet class, rule 21). | `expected 'input' to contain '[&::-webkit-search-cancel-button]:app…'` | `fix8b-04` (and round 7's `obs03-orders-search-two-crosses.png` before) |
| `DEF-WRK-9582` (P2.3) | *+ Filter ▾ › Type* lists each heading bold with its sub-types indented under it (*Connection › Commercial Connection …*); a heading still filters to itself and every sub-type (the server's own `type=`). The raise, the template builder and the edit page already used two levels; Orders was the last flat list. | `expected null not to be null` | `fix8b-03` |
| `DEF-WRK-9694` (new, WALK-B W2) | A visit row a clerk adds in a flow's *Field visit* table raises the flow's published template of the row's type (judgment 3): MVO-26-0002's *Re-read* row → WO-0044 from *Final read* v1, two tasks on its checklist. | `the typed row raised no template — the phone has no checklist` | `fix8b-11` |
| `DEF-WRK-9676` | The demo's build jobs are raised from their starter templates (36 of 39 now carry one — the three without are names no starter has); WO-0027's assign list reads *M. Chen · Missing skill: Water I*. The demo's five visit templates now carry tasks. | `module 'apps.metering.sample_data' has no attribute '_w6_template_of'` | `fix8b-12` |

**Tests.** Front end: `orderPage.dom`, `OrderDetailPage`, `OrderDetailPage.dom`, `cr168Fix8bOrders.dom` — 67/67 (14 red on the tip);
`src/features/work` + `src/components` 1,517 passed. Back end: `tests/test_cr168_fix8b.py` 6/6 (5 red on the tip) and its neighbours
(`test_def_cus_6487`, `test_us_wrk_039_from_flows`, `test_cr168_srv1_server`, `test_cr168_flowfix_flows`, `test_cr168_srv2_assign`,
`test_cr168_technician_api`, `test_def_cus_6353`, `test_def_cus_6387`, `test_cr168_srv4_flows`). `tsc` clean.

**Reds I did not cause, dated.** `ConfirmDialogTier.dom.test.tsx`'s census lacks `features/work/PartsPage.tsx` — red since `368d908d7`
(2026-10-04, lane PARTS). `test_us_wrk_039_from_flows`: `tc4` (closes on acceptance 3 of 3), `tc9` (the source vocabulary is 16, the test
says 14) and `def_wrk_3725` (*substring not found* in the move-out source) are red on `5b0e214bb` with this lane's backend files restored to
that commit's bytes — measured, not assumed.

**A probe that could not see what it measured (law 7).** Round 7's search-cross check read `getComputedStyle(input,
"::-webkit-search-cancel-button")`; Chromium answers the INPUT's own style for that pseudo-element (`auto`), fixed or not. This walk asks
the input's class and the shipped stylesheet's rule instead, and the clipped photograph shows the one ✕.

**Rollback:** redeploy `2.519.1`. No migration. Orders raised by *Duplicate* stay as ordinary jobs; the seed change reaches only a tenant
seeded after it.

## 33 · Final round — lane FIN-S: the open Work server and data defects (`2.520.4`)

Eighteen register rows handed over. Each was read, then reproduced on the tip before anything was written.

| Defect | Outcome | Evidence |
|---|---|---|
| `DEF-WRK-3635` | closed, already fixed | `9d40e708e`; `test_us_wrk_003_queue_pg.py` 4 passed on PostgreSQL 16 today |
| `DEF-WRK-4072` | **fixed** 2.520.4 | metering's event-read door refuses a row whose `unit` is not the register's; `test_def_wrk_4072_event_read_unit.py` red (`DID NOT RAISE ValidationError`) → green on PostgreSQL |
| `DEF-WRK-4073` | **fixed** 2.520.4 | `EP-WRK-09` (US-WRK-046 §1 and TC-1), `J61` and `J64` now say channel `total`; the code always did |
| `DEF-WRK-4126` | **fixed** 2.520.4 | the photo route fills `device` (request → capture-token label → User-Agent); `test_def_wrk_4126_photo_device.py` red (`'' == 'Pixel 7a'`) → green |
| `DEF-WRK-4127` | **STOPPED — not shipped** | fixing it changes what a job is charged (decision log, judgment 5): offline crew, arrive 09:00, close 10:35, sync 17:00 → today no labour line; fixed → 1.58 h × $48.50 = $76.63. For the PO |
| `DEF-WRK-4512` | closed, already fixed | `91377e779` (`work/0026`) |
| `DEF-WRK-4513`, `4117`, `4123`, `3651` | closed, already fixed | `68746f963`; a fresh `seed_demo` on PostgreSQL today: 3 crews, 4 technicians, 10 parts, 4 labour rates, 13 templates, 43 tasks, 14 materials, 13 readings |
| `DEF-WRK-6737` | **fixed** 2.520.4 | door refusal + `ck_work_orders_outcome` (`metering/0076`, 🔒, ledger row); red → green on PostgreSQL (4 passed); the migration run on a seeded database cleared a planted `completed` and audited it |
| `DEF-WRK-8537` | closed, already fixed | `831cf771b` (the seeder calls `metering_seam.accept_field_result`); `G78` PASS |
| `DEF-CUS-9696` | **fixed** 2.520.4 | `GET /disconnects/{ref}` serves `work_orders`; *The case* shows a **Visit** row linking each job; server and screen tests red → green; walked (`10-scripts/fins_disconnect_visit_walk.mjs`, all PASS; `08-qa/work-2026-10-04/final/fins-01…`, `fins-02…`) |
| `DEF-WRK-3645` | closed, already fixed | `a07db72f2`; all eleven catalogues read *Parts categories* |
| `DEF-MET-7691` | closed, already fixed | `33a9ec78f`; `buildViews.test.tsx` green |
| `DEF-MET-7812` | closed, already fixed | `4148ded57` (filed there as `DEF-MET-7805`, which never got a row) |
| `DEF-MET-6079` | **fixed** 2.520.4 | the build record's *Approved on* row; `buildRecordPanels.test.tsx` red (`expected null not to be null`) → green |
| `DEF-WRK-9697` | **left to FIN-W** | screen-only: `parse_moment` stores a date-only due as utility-zone midnight by its documented rule (decision log, judgment 4) |

**Reds I did not cause, dated (law 7):** `test_w9_event_reads.py::test_w9_transfer__task_5_one_read_serves_both_accounts` fails on `transfers.set_target_unit`, removed in `d1066469e` on 2026-09-01; already filed (`DEF-CUS-5914`, `DEF-CUS-5946`).

**Rollback:** redeploy `2.520.4`; `migrate metering 0075` drops the outcome check. Cleared outcomes are not restored; the audit trail names them.

## 34 · Final round — lane FIN-W: the open Work screen defects, each reproduced on the tip first (`2.521.1`)

**How it was measured.** PostgreSQL 16 `sbh_wfinw` (`migrate` + `seed_demo` + `load_sample_data --tenant brazosbend`), Dana,
Chromium at 1440. The tip bundle (`cad5caac6`, `2.520.2`) and the after bundle were each built `--mode compose` (the after photographs read `v2.520.3`, the number this lane held until FIN-T and FIN-S took `2.520.3`, `2.520.4` and `2.521.0` first; the code is this commit's)
and served by `07-frontend/server.mjs`; `10-scripts/cr168_finw_walk.mjs` prints one PASS/FAIL per defect and photographs
each into `08-qa/work-2026-10-04/final/finw-before-*` and `finw-after-*`. Its ONE write is WO-0019's due set to a date with
the body the order's Edit form sends (`due_at: "2026-10-09T00:00:00"`). The Escape proof is `finw-*-17-escape-after-refusal`.

**⚠ The walk's own first draft had a false wrap, recorded so nobody reuses it:** it counted the tops of the cell's whole
range, and the Schedule board's ⠿ handle sits at another top on the SAME line, so `WO-0016` read as two lines. It now
measures text nodes only (aria-hidden excluded) and reads one line — which is also why `DEF-WRK-9657` stays closed.

### 34.1 Fixed, red first (`2.521.1`)

| Defect | Red (tip) | Fix | Green |
|---|---|---|---|
| `DEF-WRK-9698` order number wraps | `finw-before-01`: `WO-` / `0016` on every row; dom test *"expected null not to be null"* (no `data-order-no` cell) | the Orders cell is `whitespace-nowrap tabular-nums` | `finw-after-01`: one line each (walk PASS) |
| `DEF-WRK-9697` date-only Due reads 00:00 | `finw-before-03`: *Due 10/09/2026 00:00*; dom test *Expected "10/06/2026" Received "10/06/2026 00:00"* | `orderFormat.dueText`: a due at the tenant's midnight reads as the date; a priority's promise keeps its minute | `finw-after-03`: *Due 10/09/2026* |
| `DEF-WRK-4637` template Loading for ever | `finw-before-06`: *Loading* under live *Edit template*; dom test *Unable to find … work.template.failedTitle* | `TemplateDetailPage` failed branch (`FailedWithRetry`, the way back kept, the commands gone); keys `work.template.failedTitle` · `notFound` · `unreadable` ×11 | `finw-after-06`: *Template unavailable · No template has this address.* |
| `DEF-MET-4973` dead end on an asset no template fits | `finw-before-15` (M-7204, sub-meter, 0 templates): a sentence and nothing to press; dom test *Unable to find role="link" and name "New template"* | a **New template** link under the refusal, to `/work/templates/new` | `finw-after-16` |
| `DEF-SHL-5771` second table type | dom test *expected [ 'w-10', … ] to not include 'font-mono'*; `finw-before-02` mono headers | `EditableTable.HEADER_TIER` = `.data-table th`'s tier (heading face, 12px token, semibold, uppercase, 0.08em, neutral-700) on the caption and every header | `finw-after-15`: computed font *Archivo*, 0.96px tracking |
| `DEF-SHL-6148` Escape dead after a refused submit | browser on the tip: after *CPL-58B is already in the register.* `activeElement` is BODY and Escape leaves the dialog open (`finw-before-17-…-b`); dom test red on `activeElement` | `ModalShell busy` — when the commit ends and focus is outside the card, focus returns to the card; `FormModal` passes `busy={working}` | after: focus on the card, Escape closes (`finw-after-17-…-a/-b`) |

**Blast radius, both ways.** `EditableTable` is every TableArray: the plan wizard's three step tables, the Work template
builder's five, the service-request, disconnect, reconnect, move-in readings and new-connection tables — header TYPE only,
no layout, the eight-consumer radius the PO confirmed on 2026-09-19. The one test asserting the old classes
(`TableArray.dom.test.tsx`) moved with it. `ModalShell.busy` is opt-in; only `FormModal` passes it, so every other
composer is unchanged; a refusal that already focused a field keeps that focus (the card is focused only when focus was lost).

### 34.2 Closed with evidence — already fixed on the tip

| Defect | Evidence |
|---|---|
| `DEF-WRK-9657` (was `invalid`) | Not reproduced, but it was REAL on the reporting bundle 2.513.0 and `c4346e159` (2.514.0) fixed it with `whitespace-nowrap`; re-closed **fixed** against that commit, because *invalid* says it never happened. `finw-before-02` one line. |
| `DEF-WRK-4104` raw key over tasks | `d34c07d5b` (2.495.0) passes `count`; `finw-before-04` |
| `DEF-WRK-4635` *raised without a template* | `a43849b99` (2.229.2); `finw-before-04` |
| `DEF-WRK-4115` `:orderNo` fed a uuid | `a43849b99` (2.229.2): the page takes either spelling and resolves a number once; `/work/orders/WO-0016` draws (`finw-before-05`). In-app links still pass the id, which the route accepts by design. |
| `DEF-WRK-4094` `?q=` ignored | `ae62b5a6a` (CR-073): all four lists seed the box from `?q=` (walk PASS ×4, `finw-before-07`) |
| `DEF-WRK-4102` / `4103` empty Rules / Labour rates | `5e502d602` and `7e2396963` (`readListPage`); 7 of 7 rules and 4 of 4 rates drawn (`finw-before-08`, `-09`) |
| `DEF-WRK-4106` *Search this list* on Performance | `43e72f9b` (`DEF-WRK-4393`) removed the dead search box; no search on the list (`finw-before-10`) |
| `DEF-WRK-4107` Crews' composition | the 2026-10-04 drawing (image 25) carries the composition as the three view counts — *Technicians 4 · Crews 2 · Contractors 1* — and `6990bb6da` (2.505.0) draws them (`finw-before-11`) |
| `DEF-WRK-3724` rationale on Templates | `45ab32e40` removed the three paragraphs and the Dashboard arrow; the one sentence left is image 43's own (`finw-before-12`) |
| `DEF-WRK-4003` no reconnect control | `8979fe2d1` and `b8e7a6c9a` (S148): *Put service back on* at `/disconnects/:ref/reconnect`, opened from a cut case, raises the visit per service (`finw-before-18-reconnect-door-DSC-26-0001.png`) |
| `DEF-RBS-4374` Work list card refuses | `88cd4cf4c` (2.445.5) released it; a live link (`finw-before-13`) |
| `DEF-WRK-9561` Map tiles | `382b89dec`: the Esri layer is mounted, CSP allows `server.arcgisonline.com`, and Chromium requests 12 tiles; this sandbox's proxy answers that host 403, so the photograph is grey with the *Tiles © Esri* attribution (`finw-before-14`) — the same limit §32's walk recorded. |
| `DEF-CUS-5161` / `DEF-CUS-6363` move-out words on move-in, transfer, request | `2bf3fe4b8` (2.350.5) and `2d23f5a5c` (2.351.0): all three wizards mount `FieldVisitOrders`, whose strings are *Field visit · No visit needed · Work orders*; the move-out sentence lives only in `RaiseFieldWork`, which **no screen mounts any more** (only its own test). Not walked to step 4 in the browser: the wizard gates it behind a vacant unit, services and a customer. |

### 34.3 Left

- **`DEF-CUS-9696`** — done by FIN-S in both halves (`5023e75d5`, `2.520.4`: the record serves `work_orders` and *The case* shows a **Visit** row), which landed while this lane was holding the screen half for exactly that read; nothing of FIN-W's was needed.
- `RaiseFieldWork`'s panel is now mounted by nothing; deleting it (and `work.fieldVisit.lead`) is a clean-up for its owner.

**Rollback:** redeploy `2.521.0`. No migration.

## 35 · Final round — lane FIN-T: the last phase tasks, the red tests and the record defects (`2.520.3` · `2.521.0` · `2.521.2`)

Judgments of ours: decision-log row *"CR-168 FINAL ROUND · FIN-T"*. Walked on PostgreSQL 16 at 1440 (`sbh_wfint`: `migrate` +
`seed_demo` + `load_sample_data --tenant brazosbend`), API on 8095, the SPA built `--mode wolocal` and served by `server.mjs` on
5227, signed in as Dana. `10-scripts/cr168_fint_preselection_walk.mjs` prints **9 PASS, 0 FAIL** over its two halves (the move-out, then `SKIP_MOVEOUT=1` for the new connection and the raised job). Photographs:
`08-qa/work-2026-10-04/final/fint-02…05-*.png`, each opened and checked not blank.

### 35.1 · The phase tasks

| Task | Outcome | Evidence |
|---|---|---|
| **P1.8** a refused save is visible | **Already done** — `cr168OrdersList.dom.test.tsx` *P1.1 — a refused save SAYS SO on the page and stays on it*, *a refused CANCEL says so too*, *a refused bulk act shows the server's sentence in the dialog* (written red first in `2.493.0`, §11: 20 of 20 red); 33 passed on `bd7b72a00` | §11 |
| **P1.9** `journeys/dispatcher-reassigns.md` | **Built** — CREATED (§7.1 found no such file), with the refusal path: *Choose why it moves.* on the page, the server's sentence in a `role="alert"` line that keeps the page | `08-qa/01-e2e/journeys/dispatcher-reassigns.md` |
| **P1.14** tell beta #27 where the materials are | **Told — the answer to the reporter, verbatim:** *"Thank you for #27. Nothing was missing — the job keeps them on its own tabs. Open Work › Orders and the job: **Parts** lists the materials planned and used; **Checklist** holds each reading's **Value** and its **Photograph** (press it to see it full size); the technician's **signature** is on **Overview** once the job is closed. On a job nobody has worked yet, *Used* is a dash on every row — that is probably what you saw. Look in build **2.521.2** (they have been there since 2.495.0)."* | §6 #27, §28.2 #27 (`06`, `09`) |
| **P2.6** the raise path on PostgreSQL | **Already done** — `tests/test_cr168_srv2_bulk_raise_pg.py`, red first in §15 (*InFailedSqlTransaction* with the per-job savepoint removed); **4 passed on PostgreSQL 16 today** | §15 |
| **P2.7** `journeys/raise-a-job.md` | **Built** | `08-qa/01-e2e/journeys/raise-a-job.md` |
| **P3.20** a door test per released control | **Built** — the released controls of P1/P3 are Approvals' *Open work orders* (P1.7), the eye (P1.5), *+ New rule* (P3.16), a rule row's open · edit · duplicate (P3.63); the Issue log (P3.11) already has its expiry test. Each now asserts the ADDRESS and the SCREEN it opens (`resolveScreen`: WRK-01, WRK-02, WRK-13, WRK-06.rule). ⚠ The Approvals case was **named after an assertion it did not make** — it proved the button enabled and never where it went; pointed at `work/map` it still passed. It now presses the button and reads the landed address: red on that mutation (*Unable to find … data-testid="landed"*), green restored | `cr168OrdersList.dom.test.tsx`, `rules/cr168Rules.dom.test.tsx` |
| **P3.21** `journeys/supervisor-writes-a-rule.md` | **Built** | `08-qa/01-e2e/journeys/supervisor-writes-a-rule.md` |
| **P3.40** each process raises on PostgreSQL, red first | **Built** — `tests/test_cr168_fint_processes_pg.py`, one case per process (**twelve** in `rule_processes.PROCESSES`: six overnight, five screen moments, the retry; the blueprint's *thirteen* was the order table's label count), and a case that fails if a process is added without one. **Red first:** with `_raise_one` stamping the MODULE again (`DEF-WRK-4096` re-introduced) the six overnight cases fail on PostgreSQL 16 — `assert 0 == 1` (refused by the CHECK) and `AssertionError: ['assets']`; restored, **13 passed** | §20.1 |
| **P3.42** customers and metering — six screens read the pre-selection | **Built** (`2.521.0`). Move-out, move-in and transfer — the *Field visit* TABLE (`FieldVisitOrders`) opens with one row per enabled rule on that moment: its template's job type, the rule's priority, its named holder, and *By rule: {name}* under the type; removable, put in once, cleared by *No visit needed*. The saved row carries `rule_id`, stamped on the job only when it is still an enabled rule on that moment of that type. **Reconnect** — the row raises the rule's template for its service. **New connection** (step 3, metering's build) — a service's row arrives on the rule's job (*Site survey · By rule: Survey every build*); step 9's commit applies the rule's priority and holder. **Routed request** — no screen of its own since *route* was retired (`BR-WRK-055` amended, `DEF-WRK-9623`); it reaches field work through its child flow. **Walk:** a rule *Final read on move-out* (High, D. Ortiz) → step 2 opens with *Reading · Re-read · High · D. Ortiz · By rule: Final read on move-out* (`fint-02`) → *Complete move-out ✓* (`fint-03`, `fint-04`) → **WO-0041** · Re-read · High · D. Ortiz, `rule_id` = the rule, listed on the rule's Jobs tab (`fint-05`); step 3's offer marks *Service drop* for an electric build and nothing for a water-only one. ⚠ The seeded *Move-in / move-out* rule names *Meter exchange — residential*, a template with no job type, so it cannot be a typed row and puts nothing on the move-in table (judgment 1) — a data fact of the demo, not a fault | `fint-02`…`fint-05`; red first: backend 6 of 6, front end 4 + 2 |
| **P3.51** no library English reaches a clerk | **Built** (`2.520.3`) — ONE fallback in the form kit: `collectFormErrors` parses with a contextual error map (ranked below a schema's own message), so a rule written without one shows *This is required.* / *That format isn't valid.* / *That value is out of range.* (`errors.val-001/002/003`, all eleven catalogues). Red first: 3 of 4 (*expected 'String must contain at least 1 charac…' to be 'This is required.'*) | `components/formLibraryEnglish.test.ts` |

### 35.2 · The red tests, each reproduced on the tip first

| Defect | On the tip | Now |
|---|---|---|
| `DEF-WRK-5108`, `9602` | 3 dispatch cases red — the fixture raised RETIRED types (*Leak investigation*, *Read verification*, *Reconnect after payment*): `order.priority is None` | live seed types (*Consumer Complaint* HIGH, *Preventive Maintenance* LOW, *No Water Supply* URGENT) + a case naming a retired type by name; 34 passed — **fixed** `bd7b72a00` |
| `DEF-WRK-4636` | `'WO-0001' == 'WO-0004'` — same cause | *Consumer Complaint*; **fixed** |
| `DEF-WRK-6486` | `assert 17 == 14`; *closed on acceptance 3 of 3* | presence of the five tokens; tc4 asserts the PO's 2026-09-19 withdrawal (`request_completion_retired` on every acceptance, tally 3 of 3); **fixed** |
| `DEF-WRK-9603` | `'BR-CUS-1024' in {'BR-CUS-083', 'BR-MET-116'}` | asserts *"common area is option"* (2026-09-21): refused only for an unidentified owner, never the retired refusal; **fixed** |
| `DEF-WRK-9604`, `4035` | *metering_seam publishes a write verb: [create_template, …, post_set_reads, …]* | the five sanctioned by-name doors listed with citations; a new verb and a stale exception both fail; **fixed** |
| `DEF-WRK-9695` | green by day, red 00:00–05:00 UTC; pinned to 04:00 UTC: `assert 18 == 17` | expected days counted in the utility's calendar at a pinned clock; **fixed** |
| `DEF-WRK-6787` | **already fixed** — 6 passed on PostgreSQL 16 today | `6933445b8` (`2.352.4`) |
| `DEF-WRK-4108` | `null value in column "dispatch_state"`, then `"held_seconds"` | the three rows written through the MODEL, so a future column's default cannot break it; run twice, idempotent — **fixed** `2.521.2` |
| `DEF-WRK-4109` | `ProtectedError … 'WorkOrderRule.template'` (six seeded rules name the template) | the old template is moved aside, its rules re-pointed at the new one, then deleted; run twice — **fixed** `2.521.2` |
| `DEF-WRK-4122` | its causes: `DEF-WRK-4096` (fixed `2.512.0`; P3.40 above) and the retire tick (on the replacement step for every asset — `AssetRetireWizard.tsx`); the script's own counts (*eight tabs*, *seven rules*) are stale against CR-168 (At risk is a tab by PO ruling 2026-10-05) and it waits for Enter — superseded by `cr168_rules_after_walk.mjs` and P3.40 | **closed fixed** |
| `DEF-SHL-5119` | at 0 ms: *Unable to find role="button" and name "Working…"* | the promise is held open by the test, no clock; 15 passed — **fixed** `f138710be` |

### 35.3 · The record defects

`DEF-WRK-3542`–`3549` **fixed** (corrected in `16-work/01-overview.md` and `05-user-stories.md`, `CR-070` stamped — `eeb27248b`,
`13c489a29`), `3550`, `3551` **fixed** (`OQ-WRK-1490`/`1493` closed, `22cffc81e`), `3570` **fixed** (`552b7476f`; no `42.04` left),
`4060` **fixed** (`d1b764869`; the four rows present), `4074` **fixed** (`f64e70bf7`), `4077` **fixed** (routed mounts exist,
`05666e3bf`; docstring `bd7b72a00`), `4082` **fixed** (the comment, `f138710be`), `4078` **wontfix** (`CrewSkill` has a reader and left
G74's baseline; the blind spot is kept on purpose), `4099` **wontfix** — both demo steps are demonstrable another way and neither was a
product fault: a job raised on an asset is listed on the asset's own *Work › Open work* tab (`GET /assets/{id}/work-orders`), and the
Maintenance history's date-keyed column is the documented design (`asset_door.py`); seeded tenants hold 0 `asset_maintenance` rows
(measured today).

### 35.4 · Reds I did not cause, dated

`tests/test_def_met_9179_build_order_service.py` — red on `bd7b72a00` with this lane's backend files at the tip's bytes; filed
**`DEF-MET-9700`** (likely `5adc6a0c9`, not bisected). `test_us_wrk_039_from_flows.py::test_def_wrk_3725…` — *substring not found* in
the move-out wizard (red on `5b0e214bb` per §32; still red). `ConfirmDialogTier.dom.test.tsx`'s census lacks `PartsPage.tsx` — red since
`368d908d7` (§32).

**Rollback:** redeploy `2.520.2` for all of §35. No migration. Rules already raised with a `rule_id` keep it; a move-out's rule row is
then simply a row the clerk can see was added for them.

## 36 · Lane WRK-FIX (2026-10-05) — three defects, red first

| Defect | Reproduced | Cause | Fix | Red → green | Version |
|---|---|---|---|---|---|
| `DEF-MET-9700` (medium) | `test_def_met_9179_build_order_service.py::test_a_template_service_the_build_does_not_carry_is_not_stamped` red on `492d316d9`: *a Water template on an electric-only build must not read Water* | `6d428bb13` (SRV-2, `DEF-WRK-9528`) made `create_work_order` copy the template's service whenever the payload's was `None`; the build commit sends `None` on purpose (`DEF-MET-9179`). Not `5adc6a0c9`, which the row guessed | `create_work_order`: on a build, the template's service is copied only when the build carries it — one rule under the commit and the build page's Raise form | 1 failed → 4 passed | `2.528.1` |
| `DEF-WRK-4127` (medium) | An offline close whose `arrive` act synced at 17:40 carried no labour line (`minutes_on_site` None) | Minutes were measured from `work_order_assignments.at`, stamped at the SYNC | PO 2026-10-05 *"allow technicain to fill in time"*: the phone's close pane carries **Arrived** and **Finished**, pre-filled from its own clock and editable; they travel on the close item and are stored server-side on the close (`labour_time`); labour = finished − arrived; the order's Overview shows both beside Accept / Send back; a re-close after a send-back reprices from the corrected pair | `test_def_wrk_4127_labour_time.py` 5 failed (`assert None == 95`, `KeyError: 'labour_time'`, …) → 7 passed (and on PostgreSQL 16, with the sync savepoint suite: 17 passed), incl. **$76.63** (1.58 h × $48.50) on the cost lines and on the report frozen at Accept; `ClosePane.dom.test.tsx` 2 failed → 15 passed | `2.529.2` |
| `DEF-WRK-9701` (low) | Orders' Due `10/9/2030` beside the order page's `10/09/2030` | `DueCell` called `toLocaleDateString()` — the browser's locale and zone | `DueCell` reads `orderFormat.dueText` with the tenant's pair (`useRegional`) | `def9701OrdersDue.dom.test.tsx`: *expected '10/9/2030' to be '10/09/2030'* → passed | `2.529.1` |

Judgments: decision log, 2026-10-05, *LANE WRK-FIX*.

Reds this lane did not cause, dated on `492d316d9` with its backend files at the tip's bytes (identical set with and without its changes, 12 of 979 cases in the 87 neighbouring test files): `test_def_wrk_9671_warehouse_job_location.py` ×3 — filed **`DEF-WRK-9711`**; `test_new_connect_step7_messages.py::test_the_letter_that_asks_for_money…` (`DEF-MET-9206`); `test_w6_connections.py::test_w6_the_gate_flag…` (`DEF-MET-4081`); `test_cr056_w5_new_connect_premises.py` tc23e/tc23f (`customers.account.identity_kind_required`); `test_def_cus_6135_…` ×2 and `test_us_wrk_039_from_flows.py::test_def_wrk_3725…` (§35.4); `test_w9_event_reads.py::test_w9_transfer__task_5…` (`transfers.set_target_unit` missing); `test_def_648_step_count_parity.py` (*server 6 steps, wizard 7*).

**Rollback:** redeploy `2.528.0` for all of §36. No migration. Closes already made with entered times keep `labour_time` in their field data, which the older build ignores (it prices from the last arrival again).
