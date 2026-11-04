# Work · the back office — the 65 images the screens are built FROM (2026-10-04)

Source: the PO's blueprint **"Work · the back office"** (claude.ai artifact `AWqx1BHqe3YSsFD4xuDQxF`, owned by the PO; built against product `2.340.0` / commit `c9aab180`). It is kept here as `blueprint.html`. Every drawing in it is the real DOM captured from the running app on 23–24 Sep 2026, with each proposed change outlined in red dashes (`[data-proposed]`) — **the dashed outlines are kept in the images on purpose: they mark what changes.**
Desktop only, 1440 wide, full page height. Rendered with Playwright/Chromium from `blueprint.html`: each drawn state's `.pw` frame unscaled (`scale(1)`, 1440px), every inner scroller expanded (none needed it), the blueprint's own webfonts loaded. All 65 were opened and checked: none blank, none clipped.

**STATUS: GO — BUILDING (PO 2026-10-04, *"go"*), as `CR-168-BRC10`.** It read *"DRAWING RECEIVED — NOT A GO TO BUILD"* until that ruling (decision log 2026-10-04, *"GO ON THE WORK BACK-OFFICE REDESIGN"*).

**How to use:**
- Build each screen from its IMAGES (B14 rule 42). PO, 2026-10-04: *"How many images you will take to build this work? I want you to build product screen using images and not text/contnt"*. `blueprint.html` and this index are an index, never the specification.
- The images decide WHAT is on the screen and HOW it is arranged. Our UI standard decides spacing, sizes, type scale, tokens and components every time (B14 rule 44; rule 38 for forms). Every selection table is the kit `TableArray`.
- Every figure in an image is an ILLUSTRATION (B14 rule 37). Real figures come from the data. The drawings were captured on the demo tenant *Brazos Bend Utilities*.
- A red dashed outline marks a proposed change; everything else in a drawing is what the product already does. A drawing tagged **Keep** (6·3g) is unchanged; **Remove** (7·2b, 7·2d) is a step the rule builder retires.
- An open native dropdown cannot be photographed; where a drawing shows one open, it is the kit's own list. Every control's source is the blueprint's *dropdown source register* (§01): **no drawing authorises a literal array in code.**
- **Superseded inside the images, and the later ruling wins:** ruling 15 (order page shape) is narrowed by ruling 17 the same day — the checklist shows on a job that is not completed too, as the plan (image 5). The four rule-builder rulings of **26 Sep** (below) post-date the 36 and are already drawn in images 57–64.
- Before go-live, photograph the built screens in the same 65 states and compare them side by side.

**Not in hand:** the companion **technician field-app document** (50 screens, 125 capabilities). Rulings **4** (sign in by email, phone or staff ID) and **36** (a contractor's people close their own jobs on the phone, with phone-only logins) land there, and ruling 6 touches the phone too. Nothing in this folder draws the phone.

## The 36 PO rulings of 23–24 September 2026

As the blueprint numbers and words them (its §00, *"Thirty-six rulings of 23 and 24 September 2026, and none is in the repository yet"*), with the PO's own words where the blueprint quotes them. Rulings 1–4 carry no date in the numbered list; the blueprint's manifest dates them 23 Sep. **None was in the repository before this commit** (searched 2026-10-04: 0 hits). They are binding and are never re-asked (hard-won law 13).

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

### Four later rulings already drawn (26 Sep 2026, on the rule builder)

The blueprint records these on the rule screens (7·2a–7·3c) and in tasks P3.64–P3.67. They are not among the 36 and are recorded here so a builder does not mistake them for proposals.

| Date | Ruling (the blueprint's words) | Narrows |
|---|---|---|
| 2026-09-26 | **The rule builder becomes three steps** — Trigger · Notify · Review; the Assignment step is retired (P3.64; images 57, 58, 59, 61). | — |
| 2026-09-26 | **Several triggers on one rule, any of them raises the job** (option B; P3.65; image 57). One subject still gets one open job per template (P3.38). | — |
| 2026-09-26 | **A notification's message is a picker into the notification catalogue, never a text box** (option A; `BR-NOT-017`, one home; image 59). | — |
| 2026-09-26 | **Escalations are rows you add** (P3.67): *Who is told* stays derived — whoever acted, plus System Admins (`BR-NOT-021`) — **and a supervisor may ADD recipients, never remove them** (option B; *Also tell*, e.g. *the area supervisor*; images 59, 61, 62). | `BR-NOT-021` clause (d) — *"no per-rule recipient is settable anywhere"* |

## Open in the blueprint (never resolved by a lane — stub with the id once minted)

- **A tile source for the map** (P3.3, 3·1) — a third-party dependency with a key and a monthly cost; the PO's decision.
- **What *SLA met* means when an order has no due date and no priority** (P5.1) — which is every order on the demo tenant.
- **Whether a tenant with a regulator may still block on a lapsed certification** (`BR-WRK-030`) — ruling 2 narrows what *block* may do.
- **A task's instruction text** (6·3c) — a new column and a migration if wanted; open until the PO says which was meant.
- `OQ-WRK-1726` (*Reconnect after payment* as a rule) is still OPEN in the register; the blueprint's ruling 10 answers its first half — yes, through the clerk's reconnect act only (`BR-PAY-036`).

## The work, once the PO says go — 7 phases, 164 tasks

Ids and titles are the blueprint's (§02); the full rows (what it involves, reference, outcome) are in `CR-168-BRC10` §5 and in `blueprint.html`. No dates: the order comes from dependency and cheapest value first. P1 carries no migration, which is why it goes first.

| Phase | Name | Tasks | Ships | Newly possible |
|---|---|---|---|---|
| P0 | Foundations | 7 | Migrations, the settings rows, the component kit, the doors nothing links to yet. | Nothing — the only phase with no user value. |
| P1 | Stop losing work | 36 | 1·1, 1·2, 1·3, 2·1 — the error path, the approval record, the approval door, real date controls. | See why a save was refused · find an order after approving it · reach an order from the approvals queue · type a date that is a date. |
| P2 | Raise a job | 21 | 1·4a, 1·4b — five fields, real pickers, the type tree, and the account door. | Actually raise a job — which is impossible today. |
| P3 | Open the doors | 67 | 5·1, 6·1, 6·3a/c/d/f/h, 7·1, 7·2 — every endpoint that is mounted and has no control. | Edit a part, retire one, filter the list · edit a task or material row · attach a help document · write and edit a rule. |
| P4 | Know where it is | 14 | 1·1, 1·2, 1·3 — acceptance, the status timeline, hold reasons, reassignment. | See that a technician accepted · read a job's timeline · say why a job is held and resume it. |
| P5 | Protect the promise | 11 | 8·1 and three new screens — the at-risk board, the schedule board, bulk raise (named, not drawn). | See what breaks today, before it breaks. |
| P6 | Tell people | 8 | Notifications and printing, per the ruling of 23 Sep. | Tell the consumer a visit is booked, moved, on the way or done · tell the back office a job is at risk · print a work order. |
| | **Total** | **164** | | |

## The images

Named `NN-<tab>-<state>.png` in the blueprint's order (01 = 1·1 … 65 = 8·1). *Class* is the blueprint's: Update (a live screen changes), New (a screen or state that does not exist today), Keep, Remove.

| # | File | Screen | Route | State | Class · phase |
|---|---|---|---|---|---|
| 1 | [01-orders-work-orders.png](images/01-orders-work-orders.png) | 1·1 | `/:tenant/work/orders · also /:tenant/work` | Work orders | Update · P1 |
| 2 | [02-orders-assign-in-bulk.png](images/02-orders-assign-in-bulk.png) | 1·1b | `/:tenant/work/orders · Assign selected…` | Assign in bulk | Update · P4 |
| 3 | [03-orders-order-overview-not-completed.png](images/03-orders-order-overview-not-completed.png) | 1·2a | `/:tenant/work/orders/:orderNo?tab=overview` | Order · Overview — not completed | Update · P1 |
| 4 | [04-orders-order-overview-completed.png](images/04-orders-order-overview-completed.png) | 1·2a′ | `/:tenant/work/orders/:orderNo?tab=overview` | Order · Overview — completed | Update · P1 |
| 5 | [05-orders-order-checklist-not-completed.png](images/05-orders-order-checklist-not-completed.png) | 1·2b | `/:tenant/work/orders/:orderNo?tab=checklist` | Order · Checklist — not completed | Update · P1 |
| 6 | [06-orders-order-checklist-completed.png](images/06-orders-order-checklist-completed.png) | 1·2b′ | `/:tenant/work/orders/:orderNo?tab=checklist` | Order · Checklist — completed | Update · P1 |
| 7 | [07-orders-order-parts.png](images/07-orders-order-parts.png) | 1·2c | `/:tenant/work/orders/:orderNo?tab=parts` | Order · Parts | Update · P1 |
| 8 | [08-orders-order-audit.png](images/08-orders-order-audit.png) | 1·2d | `/:tenant/work/orders/:orderNo?tab=audit` | Order · Audit | Update · P1 |
| 9 | [09-orders-order-photo-viewer-completed.png](images/09-orders-order-photo-viewer-completed.png) | 1·2e | `/:tenant/work/orders/:orderNo · a photograph` | Order · Photo viewer — completed | Update · P1 |
| 10 | [10-orders-order-put-on-hold.png](images/10-orders-order-put-on-hold.png) | 1·2f | `/:tenant/work/orders/:orderNo · Put on hold…` | Order · Put on hold | Update · P4 |
| 11 | [11-orders-order-cancel-order.png](images/11-orders-order-cancel-order.png) | 1·2g | `/:tenant/work/orders/:orderNo · Cancel order` | Order · Cancel order | Update · P1 |
| 12 | [12-orders-assign-a-job.png](images/12-orders-assign-a-job.png) | 1·3a | `/:tenant/work/orders/:id/edit` | Assign a job | Update · P1 |
| 13 | [13-orders-reassign-a-job.png](images/13-orders-reassign-a-job.png) | 1·3b | `/:tenant/work/orders/:id/edit` | Reassign a job | Update · P1 |
| 14 | [14-orders-raise-job-on-units.png](images/14-orders-raise-job-on-units.png) | 1·4a | `/work/orders/new?step=1` | Raise · Job — on units | Update · P2 |
| 15 | [15-orders-raise-job-an-asset-type-chosen.png](images/15-orders-raise-job-an-asset-type-chosen.png) | 1·4a′ | `/:tenant/work/orders/new?step=1` | Raise · Job — an asset type chosen | Update · P2 |
| 16 | [16-orders-raise-schedule-and-crew.png](images/16-orders-raise-schedule-and-crew.png) | 1·4b | `/work/orders/new?step=2` | Raise · Schedule & crew | Update · P2 |
| 17 | [17-orders-raise-confirm.png](images/17-orders-raise-confirm.png) | 1·4c | `/work/orders/new?step=3` | Raise · Confirm | Update · P2 |
| 18 | [18-orders-raise-result.png](images/18-orders-raise-result.png) | 1·4d | `/:tenant/work/orders/new · after the press` | Raise · Result | New · P2 |
| 19 | [19-orders-raise-from-an-account.png](images/19-orders-raise-from-an-account.png) | 1·4e | `/:tenant/accounts/:accountId/work-orders/new` | Raise · from an account | Update · P2 |
| 20 | [20-orders-raise-from-an-asset.png](images/20-orders-raise-from-an-asset.png) | 1·4f | `/:tenant/assets/:assetId/work-orders/new` | Raise · from an asset | Update · P2 |
| 21 | [21-approvals-approvals.png](images/21-approvals-approvals.png) | 2·1 | `/:tenant/work/awaiting-approval` | Approvals | Update · P1 |
| 22 | [22-approvals-approvals-accept.png](images/22-approvals-approvals-accept.png) | 2·1a | `/:tenant/work/awaiting-approval · Accept ✓` | Approvals · Accept | New · P1 |
| 23 | [23-approvals-approvals-accepted.png](images/23-approvals-approvals-accepted.png) | 2·1b | `/:tenant/work/awaiting-approval · after the press` | Approvals · Accepted | New · P1 |
| 24 | [24-map-the-day-on-the-ground.png](images/24-map-the-day-on-the-ground.png) | 3·1 | `/:tenant/work/map` | The day on the ground | Update · P3 |
| 25 | [25-crews-crews-technicians.png](images/25-crews-crews-technicians.png) | 4·1 | `/:tenant/work/crews` | Crews · Technicians | Update · P3 |
| 26 | [26-crews-add-crew-member.png](images/26-crews-add-crew-member.png) | 4·1a | `/:tenant/work/crews · + Add crew member` | Add crew member | New · P3 |
| 27 | [27-crews-crews-crews.png](images/27-crews-crews-crews.png) | 4·1b | `/:tenant/work/crews?view=crews` | Crews · Crews | Update · P3 |
| 28 | [28-crews-crews-contractors.png](images/28-crews-crews-contractors.png) | 4·1c | `/:tenant/work/crews?view=contractors` | Crews · Contractors | Update · P3 |
| 29 | [29-crews-add-a-crew.png](images/29-crews-add-a-crew.png) | 4·1d | `/:tenant/work/crews?view=crews · + Add a crew` | Add a crew | New · P3 |
| 30 | [30-crews-add-a-contractor.png](images/30-crews-add-a-contractor.png) | 4·1e | `/:tenant/work/crews?view=contractors · + Add a contractor` | Add a contractor | New · P3 |
| 31 | [31-crews-one-technician-overview.png](images/31-crews-one-technician-overview.png) | 4·2a | `/:tenant/work/crews/:slug` | One technician · Overview | Update · P3 |
| 32 | [32-crews-one-technician-jobs.png](images/32-crews-one-technician-jobs.png) | 4·2b | `/:tenant/work/crews/:slug?tab=jobs` | One technician · Jobs | New · P3 |
| 33 | [33-crews-one-technician-certifications.png](images/33-crews-one-technician-certifications.png) | 4·2c | `/:tenant/work/crews/:slug?tab=certifications` | One technician · Certifications | Update · P3 |
| 34 | [34-crews-one-technician-performance.png](images/34-crews-one-technician-performance.png) | 4·2d | `/:tenant/work/crews/:slug?tab=performance` | One technician · Performance | New · P3 |
| 35 | [35-parts-parts.png](images/35-parts-parts.png) | 5·1 | `/:tenant/work/parts` | Parts | Update · P3 |
| 36 | [36-parts-add-a-part.png](images/36-parts-add-a-part.png) | 5·1a | `/:tenant/work/parts · + Add part` | Add a part | Update · P3 |
| 37 | [37-parts-add-a-part-refused.png](images/37-parts-add-a-part-refused.png) | 5·1b | `/:tenant/work/parts · + Add part · pressed empty` | Add a part — refused | Update · P3 |
| 38 | [38-parts-import-parts-extract.png](images/38-parts-import-parts-extract.png) | 5·2a | `/:tenant/work/parts/import` | Import parts · Extract | Update · P3 |
| 39 | [39-parts-import-parts-transform.png](images/39-parts-import-parts-transform.png) | 5·2b | `/:tenant/work/parts/import` | Import parts · Transform | Update · P3 |
| 40 | [40-parts-import-parts-validate.png](images/40-parts-import-parts-validate.png) | 5·2c | `/:tenant/work/parts/import` | Import parts · Validate | Update · P3 |
| 41 | [41-parts-import-parts-load.png](images/41-parts-import-parts-load.png) | 5·2d | `/:tenant/work/parts/import` | Import parts · Load | Update · P3 |
| 42 | [42-parts-import-parts-result.png](images/42-parts-import-parts-result.png) | 5·2e | `/:tenant/work/parts/import` | Import parts · Result | Update · P3 |
| 43 | [43-templates-templates.png](images/43-templates-templates.png) | 6·1 | `/:tenant/work/templates` | Templates | Update · P3 |
| 44 | [44-templates-template-overview.png](images/44-templates-template-overview.png) | 6·2a | `/:tenant/work/templates/:id?tab=overview` | Template · Overview | Update · P3 |
| 45 | [45-templates-template-usage.png](images/45-templates-template-usage.png) | 6·2b | `/:tenant/work/templates/:id?tab=usage` | Template · Usage | Update · P3 |
| 46 | [46-templates-template-versions.png](images/46-templates-template-versions.png) | 6·2c | `/:tenant/work/templates/:id?tab=versions` | Template · Versions | Update · P3 |
| 47 | [47-templates-template-audit.png](images/47-templates-template-audit.png) | 6·2d | `/:tenant/work/templates/:id?tab=audit` | Template · Audit | Update · P3 |
| 48 | [48-templates-builder-details.png](images/48-templates-builder-details.png) | 6·3a | `/work/templates/new?step=1` | Builder · Details | Update · P3 |
| 49 | [49-templates-builder-safety.png](images/49-templates-builder-safety.png) | 6·3b | `/work/templates/new?step=2` | Builder · Safety | Update · P3 |
| 50 | [50-templates-builder-tasks.png](images/50-templates-builder-tasks.png) | 6·3c | `/work/templates/new?step=3` | Builder · Tasks | Update · P3 |
| 51 | [51-templates-builder-materials.png](images/51-templates-builder-materials.png) | 6·3d | `/work/templates/new?step=4` | Builder · Materials | Update · P3 |
| 52 | [52-templates-builder-readings.png](images/52-templates-builder-readings.png) | 6·3e | `/work/templates/new?step=5` | Builder · Readings | Update · P3 |
| 53 | [53-templates-builder-help.png](images/53-templates-builder-help.png) | 6·3f | `/work/templates/new?step=6` | Builder · Help | Update · P3 |
| 54 | [54-templates-builder-signature.png](images/54-templates-builder-signature.png) | 6·3g | `/work/templates/new?step=7` | Builder · Signature | Keep |
| 55 | [55-templates-builder-review.png](images/55-templates-builder-review.png) | 6·3h | `/work/templates/new?step=8` | Builder · Review | Update · P3 |
| 56 | [56-rules-rules.png](images/56-rules-rules.png) | 7·1 | `/:tenant/work/rules` | Rules | Update · P3 |
| 57 | [57-rules-rule-trigger.png](images/57-rules-rule-trigger.png) | 7·2a | `/work/rules/new?step=1` | Rule · Trigger | Update · P3 |
| 58 | [58-rules-rule-assignment-retired.png](images/58-rules-rule-assignment-retired.png) | 7·2b | `/work/rules/new?step=2` | Rule · Assignment — retired | Remove · P3 |
| 59 | [59-rules-rule-notify.png](images/59-rules-rule-notify.png) | 7·2c | `/work/rules/new?step=2` | Rule · Notify | Update · P3 |
| 60 | [60-rules-rule-escalation-retired.png](images/60-rules-rule-escalation-retired.png) | 7·2d | `/work/rules/new?step=4` | Rule · Escalation — retired | Remove · P3 |
| 61 | [61-rules-rule-review.png](images/61-rules-rule-review.png) | 7·2e | `/work/rules/new?step=3` | Rule · Review | Update · P3 |
| 62 | [62-rules-one-rule-overview.png](images/62-rules-one-rule-overview.png) | 7·3a | `/:tenant/work/rules/:ruleId?tab=overview` | One rule · Overview | New · P3 |
| 63 | [63-rules-one-rule-jobs.png](images/63-rules-one-rule-jobs.png) | 7·3b | `/:tenant/work/rules/:ruleId?tab=jobs` | One rule · Jobs | New · P3 |
| 64 | [64-rules-one-rule-audit.png](images/64-rules-one-rule-audit.png) | 7·3c | `/:tenant/work/rules/:ruleId?tab=audit` | One rule · Audit | New · P3 |
| 65 | [65-performance-performance.png](images/65-performance-performance.png) | 8·1 | `/:tenant/work/performance` | Performance | Update · P5 |

