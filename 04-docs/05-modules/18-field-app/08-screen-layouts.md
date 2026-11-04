# 18 · Field app — screen layouts

**One row per drawn screen — 185 images: phone 64 (FF-01 … FF-63 and the Switch technician sheet), reading mode 29
(RW-01 … RW-29), tablet 92 (FF-01 T … FF-63 T and RW-01 T … RW-29 T)** — each linking its image in `wireframes/`,
the purpose the design board gives it (its own caption), and the frame it uses.

⚠ **THE IMAGE IS THE SPECIFICATION. THIS FILE IS AN INDEX.** PO 2026-10-21, verbatim: *"please ensure all native app
screens are build using images not using text or contents"* — B14 rule 42 applied to `field-app/`. Open the PNG and
look at it before building a screen; nothing in a row below substitutes for that. **B14 rules 44 and 45 decide
construction**: sizes, spacing and touch targets come from the token module and the native type ramp, never from a
pixel in a picture (rule 37 — a figure drawn in a wireframe is an illustration). **Every tablet board carries a
board-title strip** (*"FF-17 T Tasks"*) across its top — that is the canvas labelling its board, not product chrome;
do not build it.

**How the frame column was decided.** Each board's frame was read from its source (`project/*.dc.html` on the design
canvas): whether it has the 220 px sidebar, whether a 300–360 px pane with a right border sits beside the content,
and whether that pane is the job's or the route's context (it carries *The whole job* or *Route*). **Checked by eye
on 43 of the 185 images** (phone FF-02, 05, 08, 09, 10, 12, 14, 15, 16, 20, 21, 23, 27, 33, 34, 36, 42, 43, 47, 50,
51, 63; reads RW-01, 05, 09, 17, 25, 26; tablet FF-10, 17, 25, 29, 38, 44, 50, 63 T, RW-01, 04, 07, 09, 11, 14, 27 T).
Two classifications were corrected by eye: **FF-15 T Job** is the context frame (it IS the job, so it carries no
*The whole job* link), and **RW-01 My routes** is a top-level screen whose menu icon is drawn differently. A row whose
frame looks wrong against its image: the image wins, fix the row.

---

## 1 · The frames

### Phone — six frames (390 × 844 boards)

| Code | Frame | What it is | Count |
|---|---|---|---|
| **P1** | Full screen, no navigation chrome | Before sign-in (splash, intro, sign-in, permissions, first sync) and the two route progress screens (RW-03 Download, RW-26 Sending) — a title at most, no back, the one action pinned at the foot | 9 |
| **P2** | Top level | Header with the menu ☰, the title, the alerts bell and the **sync chip** (`R103` — *"Sync is one tap from the day, never three"*); the **bottom bar Home · Jobs · Reads** (`AD-22`, `R102`) | 11 |
| **P3** | Pushed | Header with ‹ back (native back, `AD-13`), the title and at most one right action (a count *2 of 4*, a scan icon, the sync chip); the screen's primary action **pinned in a footer** at 56 pt | 63 |
| **P4** | Drawer | FF-09: the technician and the availability chip at the top; **WORK · READS · ME** sections; version and build at the foot with *Switch technician* and *Sign out* | 1 |
| **P5** | Sheet | A bottom sheet with a grab handle over a dimmed screen — a decision about the thing behind it (claim, stop, add a step, parts, reopen, availability, sign out, switch technician) | 8 |
| **P6** | Alert | FF-43 Emergency: the whole screen in the danger colour, a countdown (*Dispatch is told in 4:12*, `R28`), *Acknowledge* as the primary | 1 |

⚠ **The bottom bar is drawn two ways and the later ruling wins.** FF-10, FF-63 and RW-01 draw **Home · Jobs · Reads**
(`AD-22`, which records itself as superseding the earlier *"drawer plus one or two bottom tabs"*). FF-42 Alerts still
draws the older **Today · Alerts** bar. Build Home · Jobs · Reads on every P2 screen; FF-42's bar is a stale drawing
(B14 rule 37 settles two frames of one drawing disagreeing: build the shape they agree on — a P2 top-level screen with
a bottom bar).

### Tablet — four frames (1024 × 768 boards)

The canvas note, verbatim: *"Four frames do all 55: a centred column before you are signed in, sidebar + list +
detail, sidebar + job context + content, and sidebar + one wide pane."* And *"The drawer becomes a 220px permanent
sidebar. Nothing is behind a menu button, and the screen you are on is marked."*

| Code | Frame | Usable content width (`R121`, `R122`) | Count |
|---|---|---|---|
| **T1** | Centred column, no sidebar — before you are signed in | — | 11 |
| **T2** | 220 sidebar + 320–360 list pane + detail pane that keeps the list visible | **424 px** (1024 − 220 − 340 − 40 padding) | 31 |
| **T3** | 220 sidebar + ~300 job (or route) context pane + content | **464 px** (1024 − 220 − 300 − 40) | 34 |
| **T4** | 220 sidebar + one wide pane | **764 px** (1024 − 220 − 40) | 16 |

`R121`, written *"after twelve tablet boards shipped with two-column content in a 464 px pane"*: **a pane has a
measured width, and content is designed to that number — not to the screen's. Two columns do not fit in 464.** `R122`:
*"A fixed-width child that leaves its flexible sibling under 260 px is a broken screen, and that is arithmetic rather
than judgment, so a script finds it."*

The sidebar (FF-09 T): the technician and availability · **WORK** Home · Today · Completed · Map · Assets · Alerts ·
**READS** My routes · Find a meter · **ME** Profile · Shifts … · **VERSION 2.587.0** at the foot. The active entry
carries the brand-orange left bar.

**What width actually buys** (canvas note): *"FF-22 puts before and after side by side, which is what the office
wants to see and the phone cannot do. FF-33 Signature is the one screen a tablet is simply the right tool for — you
hand it over. FF-25 Customer gets two columns: the account on the left, the live balance pinned right where its age is
always visible."* And for reading: *"the CAPTURE screens are a phone job. A tablet in one hand while you read a meter
in a pit is the wrong tool. Where width earns its place: RW-05 puts the stop list beside the stop, RW-09 puts the
keypad beside the meter and its history, and RW-22 shows the whole route's progress at once."*

**Themes** (FF-54, FF-55, both phone and tablet): the same Today screen under dark and sunlight — *"Nothing is
re-laid out — only the tokens change. Sunlight is not a darker dark: pure black on white, 3px borders, one size up,
for noon on a driveway."*

---

## 2 · Every screen

Purposes are the design board's own caption (its `<title>`); a tablet row with no caption of its own carries its
phone twin's. The data tables behind each screen are `03-field-map.md` §11; the components are
`09-component-inventory.md`.

### 2.1 · Phone — jobs, the technician and the shell — 64 images

| Screen | Image | What it is for (the board's own caption) | Frame |
|---|---|---|---|
| **FF-01 Splash** | [`phone/FF-01-splash.png`](wireframes/phone/FF-01-splash.png) | Splash | P1 full screen |
| **FF-02 Intro 1** | [`phone/FF-02-intro-1.png`](wireframes/phone/FF-02-intro-1.png) | Intro — your day, with or without signal | P1 full screen |
| **FF-03 Intro 2** | [`phone/FF-03-intro-2.png`](wireframes/phone/FF-03-intro-2.png) | Intro — tap, do not type | P1 full screen |
| **FF-04 Intro 3** | [`phone/FF-04-intro-3.png`](wireframes/phone/FF-04-intro-3.png) | Intro — nothing is lost | P1 full screen |
| **FF-05 Sign in** | [`phone/FF-05-sign-in.png`](wireframes/phone/FF-05-sign-in.png) | Sign in | P1 full screen |
| **FF-06 Forgot password** | [`phone/FF-06-forgot-password.png`](wireframes/phone/FF-06-forgot-password.png) | Forgot password | P3 pushed |
| **FF-07 Permissions** | [`phone/FF-07-permissions.png`](wireframes/phone/FF-07-permissions.png) | Permissions — what the app needs and why | P1 full screen |
| **FF-08 First sync** | [`phone/FF-08-first-sync.png`](wireframes/phone/FF-08-first-sync.png) | First sync — load the day before you drive | P1 full screen |
| **FF-09 Menu** | [`phone/FF-09-menu.png`](wireframes/phone/FF-09-menu.png) | Menu | P4 drawer |
| **FF-10 Today** | [`phone/FF-10-today.png`](wireframes/phone/FF-10-today.png) | Today — the day's work | P2 top level |
| **FF-11 Nearby** | [`phone/FF-11-nearby.png`](wireframes/phone/FF-11-nearby.png) | Nearby — pending work around me | P2 top level |
| **FF-12 Claim** | [`phone/FF-12-claim.png`](wireframes/phone/FF-12-claim.png) | Claim — take a nearby job | P5 sheet |
| **FF-13 Map** | [`phone/FF-13-map.png`](wireframes/phone/FF-13-map.png) | Map — stops by status | P2 top level |
| **FF-14 Stop** | [`phone/FF-14-stop.png`](wireframes/phone/FF-14-stop.png) | Stop — the navigation hand-off | P5 sheet |
| **FF-15 Job** | [`phone/FF-15-job.png`](wireframes/phone/FF-15-job.png) | WO-4822 — the whole template | P3 pushed |
| **FF-16 Safety** | [`phone/FF-16-safety.png`](wireframes/phone/FF-16-safety.png) | Safety — the gate before work | P3 pushed |
| **FF-17 Tasks** | [`phone/FF-17-tasks.png`](wireframes/phone/FF-17-tasks.png) | Tasks — photos on the step, and steps added in the field | P3 pushed |
| **FF-18 Add step** | [`phone/FF-18-add-step.png`](wireframes/phone/FF-18-add-step.png) | Add step — work the template did not plan | P5 sheet |
| **FF-19 Checklist** | [`phone/FF-19-checklist.png`](wireframes/phone/FF-19-checklist.png) | Checklist — questions that branch | P3 pushed |
| **FF-20 Readings** | [`phone/FF-20-readings.png`](wireframes/phone/FF-20-readings.png) | Readings — with the photo the template asks for | P3 pushed |
| **FF-21 Photos** | [`phone/FF-21-photos.png`](wireframes/phone/FF-21-photos.png) | Photos — watermark and before/after | P3 pushed |
| **FF-22 Compare** | [`phone/FF-22-compare.png`](wireframes/phone/FF-22-compare.png) | Compare — before and after | P3 pushed |
| **FF-23 Materials** | [`phone/FF-23-materials.png`](wireframes/phone/FF-23-materials.png) | Materials — planned, used, and added in the field | P3 pushed |
| **FF-24 Parts used** | [`phone/FF-24-parts-used.png`](wireframes/phone/FF-24-parts-used.png) | Parts — what this job used | P5 sheet |
| **FF-25 Customer** | [`phone/FF-25-customer.png`](wireframes/phone/FF-25-customer.png) | Customer — employee and contractor views | P3 pushed |
| **FF-26 Restoration** | [`phone/FF-26-restoration.png`](wireframes/phone/FF-26-restoration.png) | Restoration — payment cleared, clock running | P3 pushed |
| **FF-27 Stale money** | [`phone/FF-27-stale-money.png`](wireframes/phone/FF-27-stale-money.png) | WO-4824 — stale money, warned not blocked | P3 pushed |
| **FF-28 Documents** | [`phone/FF-28-documents.png`](wireframes/phone/FF-28-documents.png) | Documents — SOPs that open with no signal | P3 pushed |
| **FF-29 Crew** | [`phone/FF-29-crew.png`](wireframes/phone/FF-29-crew.png) | Crew — two technicians, two time records | P3 pushed |
| **FF-30 Notes** | [`phone/FF-30-notes.png`](wireframes/phone/FF-30-notes.png) | Notes — remarks, stamped with who and when | P3 pushed |
| **FF-31 Activity** | [`phone/FF-31-activity.png`](wireframes/phone/FF-31-activity.png) | Activity — every status change, stamped | P3 pushed |
| **FF-32 Debrief** | [`phone/FF-32-debrief.png`](wireframes/phone/FF-32-debrief.png) | Debrief — what I did, before the close | P3 pushed |
| **FF-33 Signature** | [`phone/FF-33-signature.png`](wireframes/phone/FF-33-signature.png) | Signature — or a recorded refusal | P3 pushed |
| **FF-34 Close** | [`phone/FF-34-close.png`](wireframes/phone/FF-34-close.png) | Close — the four outcomes | P3 pushed |
| **FF-35 Completed** | [`phone/FF-35-completed.png`](wireframes/phone/FF-35-completed.png) | Completed — reopen or raise the next one | P2 top level |
| **FF-36 Reopen** | [`phone/FF-36-reopen.png`](wireframes/phone/FF-36-reopen.png) | Reopen — before the office accepts it | P5 sheet |
| **FF-37 Raise** | [`phone/FF-37-raise.png`](wireframes/phone/FF-37-raise.png) | Raise — a new order from the field | P3 pushed |
| **FF-38 Scan** | [`phone/FF-38-scan.png`](wireframes/phone/FF-38-scan.png) | Scan — verify the meter against the record | P3 pushed |
| **FF-39 Asset** | [`phone/FF-39-asset.png`](wireframes/phone/FF-39-asset.png) | Asset — W-4471 | P3 pushed |
| **FF-40 Asset history** | [`phone/FF-40-asset-history.png`](wireframes/phone/FF-40-asset-history.png) | Service history — who touched this meter | P3 pushed |
| **FF-41 Asset search** | [`phone/FF-41-asset-search.png`](wireframes/phone/FF-41-asset-search.png) | Search — find a meter | P2 top level |
| **FF-42 Alerts** | [`phone/FF-42-alerts.png`](wireframes/phone/FF-42-alerts.png) | Alerts — emergencies, changes, dispatch | P2 top level |
| **FF-43 Emergency** | [`phone/FF-43-emergency.png`](wireframes/phone/FF-43-emergency.png) | Emergency — acknowledge within five minutes | P6 alert |
| **FF-44 Profile** | [`phone/FF-44-profile.png`](wireframes/phone/FF-44-profile.png) | Profile | P2 top level |
| **FF-45 Availability** | [`phone/FF-45-availability.png`](wireframes/phone/FF-45-availability.png) | Availability — on duty, on break, off duty | P5 sheet |
| **FF-46 Shifts** | [`phone/FF-46-shifts.png`](wireframes/phone/FF-46-shifts.png) | Shifts — start the shift, and see the week | P3 pushed |
| **FF-47 Timesheet** | [`phone/FF-47-timesheet.png`](wireframes/phone/FF-47-timesheet.png) | Timesheet — where the hours went | P3 pushed |
| **FF-48 Admin tasks** | [`phone/FF-48-admin-tasks.png`](wireframes/phone/FF-48-admin-tasks.png) | Admin — work that is not a job | P2 top level |
| **FF-49 Van** | [`phone/FF-49-van.png`](wireframes/phone/FF-49-van.png) | Van — what is on the truck | P2 top level |
| **FF-50 Sync** | [`phone/FF-50-sync.png`](wireframes/phone/FF-50-sync.png) | Sync — both directions | P3 pushed |
| **FF-51 Settings** | [`phone/FF-51-settings.png`](wireframes/phone/FF-51-settings.png) | Settings | P3 pushed |
| **FF-52 Notifications** | [`phone/FF-52-notifications.png`](wireframes/phone/FF-52-notifications.png) | Notifications — sound and vibration per kind | P3 pushed |
| **FF-53 Sign out** | [`phone/FF-53-sign-out.png`](wireframes/phone/FF-53-sign-out.png) | Sign out — unsent work stays with you | P5 sheet |
| **FF-54 Dark theme** | [`phone/FF-54-dark-theme.png`](wireframes/phone/FF-54-dark-theme.png) | WO-4822 — dark theme | P3 pushed |
| **FF-55 Sunlight theme** | [`phone/FF-55-sunlight-theme.png`](wireframes/phone/FF-55-sunlight-theme.png) | WO-4822 — sunlight theme | P3 pushed |
| **FF-56 Activate** | [`phone/FF-56-activate.png`](wireframes/phone/FF-56-activate.png) | Activate your account | P3 pushed |
| **FF-57 Your password** | [`phone/FF-57-your-password.png`](wireframes/phone/FF-57-your-password.png) | Create your password | P3 pushed |
| **FF-58 Hand it back** | [`phone/FF-58-hand-it-back.png`](wireframes/phone/FF-58-hand-it-back.png) | Hand the job back | P3 pushed |
| **FF-59 Add a reading** | [`phone/FF-59-add-a-reading.png`](wireframes/phone/FF-59-add-a-reading.png) | Add a reading the template did not ask for | P3 pushed |
| **FF-60 Asset papers** | [`phone/FF-60-asset-papers.png`](wireframes/phone/FF-60-asset-papers.png) | Documents for a new asset | P3 pushed |
| **FF-61 Reconnect** | [`phone/FF-61-reconnect.png`](wireframes/phone/FF-61-reconnect.png) | Reconnect — the fee is its own question | P3 pushed |
| **FF-62 Pick a template** | [`phone/FF-62-pick-a-template.png`](wireframes/phone/FF-62-pick-a-template.png) | Pick a template | P3 pushed |
| **FF-63 Home** | [`phone/FF-63-home.png`](wireframes/phone/FF-63-home.png) | Home — both modules at a glance | P2 top level |
| **Switch technician** | [`phone/Switch.png`](wireframes/phone/Switch.png) | Switch technician — the shared handset | P5 sheet |

### 2.2 · Phone — reading a route (RW) — 29 images

| Screen | Image | What it is for (the board's own caption) | Frame |
|---|---|---|---|
| **RW-01 My routes** | [`reads/RW-01-my-routes.png`](wireframes/reads/RW-01-my-routes.png) | My routes | P2 top level |
| **RW-02 Route summary** | [`reads/RW-02-route-summary.png`](wireframes/reads/RW-02-route-summary.png) | Route summary | P3 pushed |
| **RW-03 Download** | [`reads/RW-03-download.png`](wireframes/reads/RW-03-download.png) | Downloading the route | P1 full screen |
| **RW-04 Route map** | [`reads/RW-04-route-map.png`](wireframes/reads/RW-04-route-map.png) | Route map | P3 pushed |
| **RW-05 The walk** | [`reads/RW-05-the-walk.png`](wireframes/reads/RW-05-the-walk.png) | The walk — nearest first, or the office order | P3 pushed |
| **RW-06 The stop** | [`reads/RW-06-the-stop.png`](wireframes/reads/RW-06-the-stop.png) | The stop — every meter at one address | P3 pushed |
| **RW-07 Getting in** | [`reads/RW-07-getting-in.png`](wireframes/reads/RW-07-getting-in.png) | Access and notes | P3 pushed |
| **RW-08 Find a meter** | [`reads/RW-08-find-a-meter.png`](wireframes/reads/RW-08-find-a-meter.png) | Find a meter | P3 pushed |
| **RW-09 Read entry** | [`reads/RW-09-read-entry.png`](wireframes/reads/RW-09-read-entry.png) | Read entry — a reading is a number plus four more things | P3 pushed |
| **RW-10 Dials** | [`reads/RW-10-dials.png`](wireframes/reads/RW-10-dials.png) | Dial entry | P3 pushed |
| **RW-11 Scan to confirm** | [`reads/RW-11-scan-to-confirm.png`](wireframes/reads/RW-11-scan-to-confirm.png) | Scan to confirm the meter | P3 pushed |
| **RW-12 Master and subs** | [`reads/RW-12-master-and-subs.png`](wireframes/reads/RW-12-master-and-subs.png) | Master and sub-meters | P3 pushed |
| **RW-13 The reading** | [`reads/RW-13-the-reading.png`](wireframes/reads/RW-13-the-reading.png) | The reading record — everything one reading carries | P3 pushed |
| **RW-14 The camera** | [`reads/RW-14-the-camera.png`](wireframes/reads/RW-14-the-camera.png) | The camera — stamped as it is taken | P3 pushed |
| **RW-15 High or low** | [`reads/RW-15-high-or-low.png`](wireframes/reads/RW-15-high-or-low.png) | Higher than expected — warned, never blocked | P3 pushed |
| **RW-16 Second look** | [`reads/RW-16-second-look.png`](wireframes/reads/RW-16-second-look.png) | Read it again | P3 pushed |
| **RW-17 Can't read** | [`reads/RW-17-can-t-read.png`](wireframes/reads/RW-17-can-t-read.png) | Can't read — eight seeded reasons, tenant-extensible | P3 pushed |
| **RW-18 Different meter** | [`reads/RW-18-different-meter.png`](wireframes/reads/RW-18-different-meter.png) | Not the meter on the list | P3 pushed |
| **RW-19 Not on the route** | [`reads/RW-19-not-on-the-route.png`](wireframes/reads/RW-19-not-on-the-route.png) | A meter that is not on the route | P3 pushed |
| **RW-20 Add a meter** | [`reads/RW-20-add-a-meter.png`](wireframes/reads/RW-20-add-a-meter.png) | Add a meter from the field | P3 pushed |
| **RW-21 Raise it** | [`reads/RW-21-raise-it.png`](wireframes/reads/RW-21-raise-it.png) | Raise work from the route | P3 pushed |
| **RW-22 Where you are** | [`reads/RW-22-where-you-are.png`](wireframes/reads/RW-22-where-you-are.png) | Route progress | P3 pushed |
| **RW-23 Still to do** | [`reads/RW-23-still-to-do.png`](wireframes/reads/RW-23-still-to-do.png) | Still to do | P3 pushed |
| **RW-24 Photos** | [`reads/RW-24-photos.png`](wireframes/reads/RW-24-photos.png) | The day's photos | P3 pushed |
| **RW-25 Turn it in** | [`reads/RW-25-turn-it-in.png`](wireframes/reads/RW-25-turn-it-in.png) | Turn in the route | P3 pushed |
| **RW-26 Sending** | [`reads/RW-26-sending.png`](wireframes/reads/RW-26-sending.png) | Sending the route | P1 full screen |
| **RW-27 Turned in** | [`reads/RW-27-turned-in.png`](wireframes/reads/RW-27-turned-in.png) | Turned in — the receipt | P3 pushed |
| **RW-28 My reads** | [`reads/RW-28-my-reads.png`](wireframes/reads/RW-28-my-reads.png) | What I have read | P3 pushed |
| **RW-29 Reading settings** | [`reads/RW-29-reading-settings.png`](wireframes/reads/RW-29-reading-settings.png) | Reading settings | P3 pushed |

### 2.3 · Tablet — the same screens in four frames — 92 images

| Screen | Image | What it is for (the board's own caption) | Frame |
|---|---|---|---|
| **FF-01 T Splash** | [`tablet/FF-01-T-splash.png`](wireframes/tablet/FF-01-T-splash.png) | Splash | T1 centred column |
| **FF-02 T Intro 1** | [`tablet/FF-02-T-intro-1.png`](wireframes/tablet/FF-02-T-intro-1.png) | Intro — your day, with or without signal | T1 centred column |
| **FF-03 T Intro 2** | [`tablet/FF-03-T-intro-2.png`](wireframes/tablet/FF-03-T-intro-2.png) | Intro — tap, do not type | T1 centred column |
| **FF-04 T Intro 3** | [`tablet/FF-04-T-intro-3.png`](wireframes/tablet/FF-04-T-intro-3.png) | Intro — nothing is lost | T1 centred column |
| **FF-05 T Sign in** | [`tablet/FF-05-T-sign-in.png`](wireframes/tablet/FF-05-T-sign-in.png) | Sign in | T1 centred column |
| **FF-06 T Forgot password** | [`tablet/FF-06-T-forgot-password.png`](wireframes/tablet/FF-06-T-forgot-password.png) | Forgot password | T1 centred column |
| **FF-07 T Permissions** | [`tablet/FF-07-T-permissions.png`](wireframes/tablet/FF-07-T-permissions.png) | Permissions — what the app needs and why | T1 centred column |
| **FF-08 T First sync** | [`tablet/FF-08-T-first-sync.png`](wireframes/tablet/FF-08-T-first-sync.png) | First sync — load the day before you drive | T1 centred column |
| **FF-09 T The sidebar** | [`tablet/FF-09-T-the-sidebar.png`](wireframes/tablet/FF-09-T-the-sidebar.png) | Menu | T4 sidebar + one wide pane |
| **FF-10 T Today** | [`tablet/FF-10-T-today.png`](wireframes/tablet/FF-10-T-today.png) | Today beside the job | T2 sidebar + list + detail |
| **FF-11 T Nearby** | [`tablet/FF-11-T-nearby.png`](wireframes/tablet/FF-11-T-nearby.png) | Nearby — pending work around me | T2 sidebar + list + detail |
| **FF-12 T Claim** | [`tablet/FF-12-T-claim.png`](wireframes/tablet/FF-12-T-claim.png) | Claim — take a nearby job | T2 sidebar + list + detail |
| **FF-13 T Map** | [`tablet/FF-13-T-map.png`](wireframes/tablet/FF-13-T-map.png) | Stops beside the map | T2 sidebar + list + detail |
| **FF-14 T The stop** | [`tablet/FF-14-T-the-stop.png`](wireframes/tablet/FF-14-T-the-stop.png) | Stop — the navigation hand-off | T3 sidebar + context + content |
| **FF-15 T Job** | [`tablet/FF-15-T-job.png`](wireframes/tablet/FF-15-T-job.png) | The job with its tasks beside it | T3 sidebar + context + content |
| **FF-16 T Safety** | [`tablet/FF-16-T-safety.png`](wireframes/tablet/FF-16-T-safety.png) | Safety — the gate before work | T3 sidebar + context + content |
| **FF-17 T Tasks** | [`tablet/FF-17-T-tasks.png`](wireframes/tablet/FF-17-T-tasks.png) | Tasks — photos on the step, and steps added in the field | T3 sidebar + context + content |
| **FF-18 T Add a step** | [`tablet/FF-18-T-add-a-step.png`](wireframes/tablet/FF-18-T-add-a-step.png) | Add step — work the template did not plan | T3 sidebar + context + content |
| **FF-19 T Checklist** | [`tablet/FF-19-T-checklist.png`](wireframes/tablet/FF-19-T-checklist.png) | Checklist — questions that branch | T3 sidebar + context + content |
| **FF-20 T Readings** | [`tablet/FF-20-T-readings.png`](wireframes/tablet/FF-20-T-readings.png) | Readings in two columns | T4 sidebar + one wide pane |
| **FF-21 T Photos** | [`tablet/FF-21-T-photos.png`](wireframes/tablet/FF-21-T-photos.png) | The photo gallery, grouped by what it proves | T4 sidebar + one wide pane |
| **FF-22 T Before and after** | [`tablet/FF-22-T-before-and-after.png`](wireframes/tablet/FF-22-T-before-and-after.png) | Compare — before and after | T3 sidebar + context + content |
| **FF-23 T Materials** | [`tablet/FF-23-T-materials.png`](wireframes/tablet/FF-23-T-materials.png) | Materials — planned, used, and added in the field | T3 sidebar + context + content |
| **FF-24 T Parts used** | [`tablet/FF-24-T-parts-used.png`](wireframes/tablet/FF-24-T-parts-used.png) | Parts — what this job used | T3 sidebar + context + content |
| **FF-25 T Customer** | [`tablet/FF-25-T-customer.png`](wireframes/tablet/FF-25-T-customer.png) | Customer — employee and contractor views | T3 sidebar + context + content |
| **FF-26 T Restoration** | [`tablet/FF-26-T-restoration.png`](wireframes/tablet/FF-26-T-restoration.png) | Restoration — payment cleared, clock running | T3 sidebar + context + content |
| **FF-27 T Disconnect** | [`tablet/FF-27-T-disconnect.png`](wireframes/tablet/FF-27-T-disconnect.png) | WO-4824 — stale money, warned not blocked | T3 sidebar + context + content |
| **FF-28 T Documents** | [`tablet/FF-28-T-documents.png`](wireframes/tablet/FF-28-T-documents.png) | Documents — SOPs that open with no signal | T2 sidebar + list + detail |
| **FF-29 T Crew** | [`tablet/FF-29-T-crew.png`](wireframes/tablet/FF-29-T-crew.png) | Crew — two technicians, two time records | T2 sidebar + list + detail |
| **FF-30 T Notes** | [`tablet/FF-30-T-notes.png`](wireframes/tablet/FF-30-T-notes.png) | Notes — remarks, stamped with who and when | T3 sidebar + context + content |
| **FF-31 T Activity** | [`tablet/FF-31-T-activity.png`](wireframes/tablet/FF-31-T-activity.png) | Activity — every status change, stamped | T2 sidebar + list + detail |
| **FF-32 T Debrief** | [`tablet/FF-32-T-debrief.png`](wireframes/tablet/FF-32-T-debrief.png) | Debrief — what I did, before the close | T3 sidebar + context + content |
| **FF-33 T Signature** | [`tablet/FF-33-T-signature.png`](wireframes/tablet/FF-33-T-signature.png) | Signature — or a recorded refusal | T3 sidebar + context + content |
| **FF-34 T Close** | [`tablet/FF-34-T-close.png`](wireframes/tablet/FF-34-T-close.png) | Close — the four outcomes | T3 sidebar + context + content |
| **FF-35 T Completed** | [`tablet/FF-35-T-completed.png`](wireframes/tablet/FF-35-T-completed.png) | Completed work beside its record | T2 sidebar + list + detail |
| **FF-36 T Reopen** | [`tablet/FF-36-T-reopen.png`](wireframes/tablet/FF-36-T-reopen.png) | Reopen — before the office accepts it | T3 sidebar + context + content |
| **FF-37 T Raise an order** | [`tablet/FF-37-T-raise-an-order.png`](wireframes/tablet/FF-37-T-raise-an-order.png) | Raise — a new order from the field | T3 sidebar + context + content |
| **FF-38 T Scan** | [`tablet/FF-38-T-scan.png`](wireframes/tablet/FF-38-T-scan.png) | Scan — verify the meter against the record | T4 sidebar + one wide pane |
| **FF-39 T Asset** | [`tablet/FF-39-T-asset.png`](wireframes/tablet/FF-39-T-asset.png) | Asset beside its history | T2 sidebar + list + detail |
| **FF-40 T Asset history** | [`tablet/FF-40-T-asset-history.png`](wireframes/tablet/FF-40-T-asset-history.png) | Service history — who touched this meter | T2 sidebar + list + detail |
| **FF-41 T Asset search** | [`tablet/FF-41-T-asset-search.png`](wireframes/tablet/FF-41-T-asset-search.png) | Search — find a meter | T2 sidebar + list + detail |
| **FF-42 T Alerts** | [`tablet/FF-42-T-alerts.png`](wireframes/tablet/FF-42-T-alerts.png) | Alerts beside the one you opened | T2 sidebar + list + detail |
| **FF-43 T Emergency** | [`tablet/FF-43-T-emergency.png`](wireframes/tablet/FF-43-T-emergency.png) | Emergency — acknowledge within five minutes | T2 sidebar + list + detail |
| **FF-44 T Profile** | [`tablet/FF-44-T-profile.png`](wireframes/tablet/FF-44-T-profile.png) | Profile | T2 sidebar + list + detail |
| **FF-45 T Availability** | [`tablet/FF-45-T-availability.png`](wireframes/tablet/FF-45-T-availability.png) | Availability — on duty, on break, off duty | T2 sidebar + list + detail |
| **FF-46 T Shifts** | [`tablet/FF-46-T-shifts.png`](wireframes/tablet/FF-46-T-shifts.png) | Shifts — start the shift, and see the week | T2 sidebar + list + detail |
| **FF-47 T Timesheet** | [`tablet/FF-47-T-timesheet.png`](wireframes/tablet/FF-47-T-timesheet.png) | Timesheet — where the hours went | T2 sidebar + list + detail |
| **FF-48 T Admin** | [`tablet/FF-48-T-admin.png`](wireframes/tablet/FF-48-T-admin.png) | Admin — work that is not a job | T2 sidebar + list + detail |
| **FF-49 T Van** | [`tablet/FF-49-T-van.png`](wireframes/tablet/FF-49-T-van.png) | Van — what is on the truck | T2 sidebar + list + detail |
| **FF-50 T Sync** | [`tablet/FF-50-T-sync.png`](wireframes/tablet/FF-50-T-sync.png) | Sync — both directions | T2 sidebar + list + detail |
| **FF-51 T Settings** | [`tablet/FF-51-T-settings.png`](wireframes/tablet/FF-51-T-settings.png) | Settings | T2 sidebar + list + detail |
| **FF-52 T Notifications** | [`tablet/FF-52-T-notifications.png`](wireframes/tablet/FF-52-T-notifications.png) | Notifications — sound and vibration per kind | T2 sidebar + list + detail |
| **FF-53 T Sign out** | [`tablet/FF-53-T-sign-out.png`](wireframes/tablet/FF-53-T-sign-out.png) | Sign out — unsent work stays with you | T1 centred column |
| **FF-54 T Dark** | [`tablet/FF-54-T-dark.png`](wireframes/tablet/FF-54-T-dark.png) | WO-4822 — dark theme | T4 sidebar + one wide pane |
| **FF-55 T Sunlight** | [`tablet/FF-55-T-sunlight.png`](wireframes/tablet/FF-55-T-sunlight.png) | WO-4822 — sunlight theme | T4 sidebar + one wide pane |
| **FF-56 T Activate** | [`tablet/FF-56-T-activate.png`](wireframes/tablet/FF-56-T-activate.png) | Activate your account | T1 centred column |
| **FF-57 T Your password** | [`tablet/FF-57-T-your-password.png`](wireframes/tablet/FF-57-T-your-password.png) | Create your password | T1 centred column |
| **FF-58 T Hand it back** | [`tablet/FF-58-T-hand-it-back.png`](wireframes/tablet/FF-58-T-hand-it-back.png) | Hand the job back | T3 sidebar + context + content |
| **FF-59 T Add a reading** | [`tablet/FF-59-T-add-a-reading.png`](wireframes/tablet/FF-59-T-add-a-reading.png) | Add a reading the template did not ask for | T3 sidebar + context + content |
| **FF-60 T Asset papers** | [`tablet/FF-60-T-asset-papers.png`](wireframes/tablet/FF-60-T-asset-papers.png) | Documents for a new asset | T3 sidebar + context + content |
| **FF-61 T Reconnect** | [`tablet/FF-61-T-reconnect.png`](wireframes/tablet/FF-61-T-reconnect.png) | Reconnect — the fee is its own question | T3 sidebar + context + content |
| **FF-62 T Pick a template** | [`tablet/FF-62-T-pick-a-template.png`](wireframes/tablet/FF-62-T-pick-a-template.png) | Pick a template | T2 sidebar + list + detail |
| **FF-63 T Home** | [`tablet/FF-63-T-home.png`](wireframes/tablet/FF-63-T-home.png) | Home — both modules at a glance | T4 sidebar + one wide pane |
| **RW-01 T My routes** | [`tablet/RW-01-T-my-routes.png`](wireframes/tablet/RW-01-T-my-routes.png) | My routes | T2 sidebar + list + detail |
| **RW-02 T Route summary** | [`tablet/RW-02-T-route-summary.png`](wireframes/tablet/RW-02-T-route-summary.png) | Route summary | T4 sidebar + one wide pane |
| **RW-03 T Download** | [`tablet/RW-03-T-download.png`](wireframes/tablet/RW-03-T-download.png) | Downloading the route | T4 sidebar + one wide pane |
| **RW-04 T Route map** | [`tablet/RW-04-T-route-map.png`](wireframes/tablet/RW-04-T-route-map.png) | Route map | T4 sidebar + one wide pane |
| **RW-05 T The walk** | [`tablet/RW-05-T-the-walk.png`](wireframes/tablet/RW-05-T-the-walk.png) | The walk — nearest first, or the office order | T2 sidebar + list + detail |
| **RW-06 T The stop** | [`tablet/RW-06-T-the-stop.png`](wireframes/tablet/RW-06-T-the-stop.png) | The stop — every meter at one address | T2 sidebar + list + detail |
| **RW-07 T Getting in** | [`tablet/RW-07-T-getting-in.png`](wireframes/tablet/RW-07-T-getting-in.png) | Access and notes | T4 sidebar + one wide pane |
| **RW-08 T Find a meter** | [`tablet/RW-08-T-find-a-meter.png`](wireframes/tablet/RW-08-T-find-a-meter.png) | Find a meter | T2 sidebar + list + detail |
| **RW-09 T Read entry** | [`tablet/RW-09-T-read-entry.png`](wireframes/tablet/RW-09-T-read-entry.png) | Read entry — a reading is a number plus four more things | T3 sidebar + context + content |
| **RW-10 T Dials** | [`tablet/RW-10-T-dials.png`](wireframes/tablet/RW-10-T-dials.png) | Dial entry | T3 sidebar + context + content |
| **RW-11 T Scan to confirm** | [`tablet/RW-11-T-scan-to-confirm.png`](wireframes/tablet/RW-11-T-scan-to-confirm.png) | Scan to confirm the meter | T4 sidebar + one wide pane |
| **RW-12 T Master and subs** | [`tablet/RW-12-T-master-and-subs.png`](wireframes/tablet/RW-12-T-master-and-subs.png) | Master and sub-meters | T2 sidebar + list + detail |
| **RW-13 T The reading** | [`tablet/RW-13-T-the-reading.png`](wireframes/tablet/RW-13-T-the-reading.png) | The reading record — everything one reading carries | T3 sidebar + context + content |
| **RW-14 T The camera** | [`tablet/RW-14-T-the-camera.png`](wireframes/tablet/RW-14-T-the-camera.png) | The camera — stamped as it is taken | T4 sidebar + one wide pane |
| **RW-15 T High or low** | [`tablet/RW-15-T-high-or-low.png`](wireframes/tablet/RW-15-T-high-or-low.png) | Higher than expected — warned, never blocked | T3 sidebar + context + content |
| **RW-16 T Second look** | [`tablet/RW-16-T-second-look.png`](wireframes/tablet/RW-16-T-second-look.png) | Read it again | T3 sidebar + context + content |
| **RW-17 T Can't read** | [`tablet/RW-17-T-can-t-read.png`](wireframes/tablet/RW-17-T-can-t-read.png) | Can't read — eight seeded reasons, tenant-extensible | T3 sidebar + context + content |
| **RW-18 T Different meter** | [`tablet/RW-18-T-different-meter.png`](wireframes/tablet/RW-18-T-different-meter.png) | Not the meter on the list | T3 sidebar + context + content |
| **RW-19 T Not on the route** | [`tablet/RW-19-T-not-on-the-route.png`](wireframes/tablet/RW-19-T-not-on-the-route.png) | A meter that is not on the route | T3 sidebar + context + content |
| **RW-20 T Add a meter** | [`tablet/RW-20-T-add-a-meter.png`](wireframes/tablet/RW-20-T-add-a-meter.png) | Add a meter from the field | T3 sidebar + context + content |
| **RW-21 T Raise it** | [`tablet/RW-21-T-raise-it.png`](wireframes/tablet/RW-21-T-raise-it.png) | Raise work from the route | T3 sidebar + context + content |
| **RW-22 T Where you are** | [`tablet/RW-22-T-where-you-are.png`](wireframes/tablet/RW-22-T-where-you-are.png) | Route progress | T3 sidebar + context + content |
| **RW-23 T Still to do** | [`tablet/RW-23-T-still-to-do.png`](wireframes/tablet/RW-23-T-still-to-do.png) | Still to do | T2 sidebar + list + detail |
| **RW-24 T Photos** | [`tablet/RW-24-T-photos.png`](wireframes/tablet/RW-24-T-photos.png) | The day's photos | T4 sidebar + one wide pane |
| **RW-25 T Turn it in** | [`tablet/RW-25-T-turn-it-in.png`](wireframes/tablet/RW-25-T-turn-it-in.png) | Turn in the route | T3 sidebar + context + content |
| **RW-26 T Sending** | [`tablet/RW-26-T-sending.png`](wireframes/tablet/RW-26-T-sending.png) | Sending the route | T4 sidebar + one wide pane |
| **RW-27 T Turned in** | [`tablet/RW-27-T-turned-in.png`](wireframes/tablet/RW-27-T-turned-in.png) | Turned in — the receipt | T4 sidebar + one wide pane |
| **RW-28 T My reads** | [`tablet/RW-28-T-my-reads.png`](wireframes/tablet/RW-28-T-my-reads.png) | What I have read | T2 sidebar + list + detail |
| **RW-29 T Reading settings** | [`tablet/RW-29-T-reading-settings.png`](wireframes/tablet/RW-29-T-reading-settings.png) | Reading settings | T2 sidebar + list + detail |

