# 18 · Field app — component inventory

**Every reusable piece the screen images show, each defined once in `field-app/src/components/`, and mapped to the
web kit's equivalent in `07-frontend/src/components/` where one exists.** Written by LOOKING at the images in
`wireframes/` — 43 of the 185 were opened for this file and `08-screen-layouts.md` (*How the frame column was
decided*) lists them — never from the design's text.

**Three rulings decide how this kit is built:**

* **Same names and props as the web kit, different rendering** — decision log 2026-10-21, conflict 10: *"the native
  kit in the field app's own `src/components`, same component names and props as the web kit, different rendering"*.
  So where a web component exists, **the native component IS that name** — the *Component* column below already
  uses it. Where the native piece has no web twin it gets a name of its own, and a later web twin takes that name,
  not the other way round. **Never a second name for a thing the web already names.**
* **A piece of UI is a component; standalone code inside a page is not reuse** (B14 rule 43; T-07). A screen
  imports; it never defines a control inline (`11-technology.md` §6).
* **Construction comes from the standard, not the picture** (B14 rules 44, 45; rule 37). Sizes are tokens: primary
  action **56 pt**, any control **48 pt**, **8 pt** clearance; type **22 / 17 / 15 / 13 / 12**; radius **4 / 6 / 8 /
  22** (chip, button, card, pill); spacing only the seven steps of the 4 px scale; button fill `brand-action`
  `#e12e13`, never `#ec3013` (`11-technology.md` §2). A pixel measured off a PNG is never a value.

**Count: 45 components — 25 take an existing web component's name, 20 are native-only** (§7). By group: frames and
navigation 10 · signals and status 9 · cards and rows 10 · inputs and controls 9 · capture and evidence 4 · states 3.
T-07's own minimum list — *"button in three tiers and two sizes, field with its 5/6/20 px anatomy, card, list row,
status chip, sheet, empty state, toast"* — is all here: `Button`, `TextField`, `Panel`, `ListRow`, `StatusPill`,
`ConfirmDialog`, `EmptyList`, `Toast`.

---

## 1 · Frames and navigation — 10

| Component | What the images show | Seen on | Web kit |
|---|---|---|---|
| `AppShell` | The frame: header + body + optional footer + optional bottom bar on a phone (frames P1–P6); the 220 px permanent sidebar beside one, two or three panes on a tablet (T1–T4) | every screen | `AppShell.tsx` |
| `PageHeader` | ☰ or ‹ back · the title at 22 · one right slot (a count *2 of 4*, a scan icon, *Dials*, *Mark read*, the bell with its badge, the sync chip) | FF-10, 15, 16, 20, 23, 47; RW-05, 09 | `PageHeader.tsx` (kicker / title / backTo / actions) |
| `BottomBar` | Three tabs with icons — **Home · Jobs · Reads**, the active one in brand orange (`AD-22`). FF-42 still draws the older *Today · Alerts*; the later ruling wins (`08-screen-layouts.md` §1) | FF-10, FF-63, RW-01 | none — native-only |
| `Drawer` | Phone drawer and tablet sidebar, one component: the technician with an initials avatar and the availability chip; **WORK · READS · ME** sections in brand-orange caps; rows with icon, label and a right count (*11*, *15 left*, a red badge); the active row with an orange left bar; **VERSION 2.587.0 · build 412** at the foot; *Switch technician* · *Sign out* | FF-09, every tablet board | none as a component — it renders `AppShell`'s `visibleNavItems` |
| `PaneLayout` | Tablet split with measured widths — list 320–360, context ~300, content flexible, **never leaving a sibling under 260 px** (`R121`, `R122`) | FF-10 T, FF-17 T, FF-44 T | none — native-only |
| `ContextPane` | The tablet's left pane for an open job (*WORK ORDER · WO-4821 · Meter exchange · P2 · Where · Customer · Clocks · The whole job*) or route (*ROUTE · Maple Heights · Progress 136 of 151 · Where · The walk · Progress*) | FF-17 T, FF-25 T, RW-09 T | none — native-only |
| `StickyFooter` | The pinned action area: one full-width 56 pt primary; or a secondary + primary pair (*Notes* + *Continue — step 4 of 8*, *All 11 photos* + *Debrief*); or a primary over a danger-tier outline (*Go and read the 15* / *Turn in 136 of 151*) | FF-15, 16, 20, 27, 34; RW-25; FF-10 T | none — native-only |
| `ConfirmDialog` | The **bottom sheet**: grab handle over a dimmed screen, a question title (*Take this job?*, *Reopen WO-4822?*), a fact card, a warning line, *Cancel* + the commit (danger tier when it undoes something) | FF-12, FF-14, FF-36, FF-53 | `ConfirmDialog.tsx` (tier, consequence, commit) |
| `FullScreenAlert` | The emergency: whole screen danger red, icon, *EMERGENCY · P1* kicker, title, fact card, *What was said*, the countdown card (*Dispatch is told in 4:12*, `R28`), *Acknowledge* + *Call dispatch* · *Cannot attend* | FF-43 | none — native-only |
| `MapView` | Street tiles with numbered stop pins (next dark, read green, could-not amber, to-do grey, *you* blue) and a legend; **offline it shows an offline state** (`R31`); a sheet or side card for the nearest stop | FF-13, FF-14, RW-04 T | none — native-only (Esri tiles, `AD-06`) |

## 2 · Signals and status — 9

| Component | What the images show | Seen on | Web kit |
|---|---|---|---|
| `StatusPill` | Coloured caps chip — *ON SITE*, *DISPATCHED*, *QUEUED*, *UNASSIGNED*, *CONNECTED*, *ON THE PHONE*, *NOT DOWNLOADED*, *VALID*, *38 DAYS*, *REQUIRED*; and the **priority badge** *P1 / P2 / P3* as a tone of the same pill — a badge that **never reorders** (`R1`, `BR-WRK-035`) | FF-10, 12, 15, 21, 27, 50; RW-01; FF-44 T | `StatusPill.tsx` |
| `CountBadge` | Red round count on the bell and beside *Alerts* | FF-10, FF-09, FF-42 | `CountBadge.tsx` |
| `Chip` | A pill with a dot or a label — the **availability chip** (green dot + *Available*, opens FF-45) and every **choice chip** on Settings (language, date, clock, units, theme — the chosen one filled dark; `R38`: choices over keyboards) | FF-10, FF-09, FF-51 | `Chip.tsx` |
| `SyncChip` | Header chip: sync icon + the number waiting (*12*, *62*), amber when work waits; on a job *12 to send* with the connection icon; on a stale job the signal icon + *71%*. `R32`: *"The icon carries the connection; the number carries the sync"*; `R103`: one tap opens Sync | FF-10, 15, 27; RW-01 | none — native-only |
| `WarningBox` | Full-width tinted strip with an icon and one sentence, four tones — warning *Tasks stay locked. All four required.*; danger *1 required photo missing*; success *On depot wifi. About 40 seconds.*; info *Needs a signal.* | FF-16, 34, 08; FF-25 T | `WarningBox.tsx` |
| `ConsequenceBox` | A bordered tinted box inside a card, title + body + optional action — *Outside expected range. Enter it again.* + *Enter again*; *15 not read at all* + *See the five*; *3 · Close the valve — Proceeding is recorded as unverified*; *NOT ON YOUR VAN* + *Ask the depot* | FF-20, 23, 27; RW-25 | `ConsequenceBox.tsx` |
| `AgeCell` | The age of a figure, said out loud — the money card's band *BALANCE IS 3 DAYS OLD* (warning) and *Read 40 seconds ago* (green dot) — `R17`'s five-minute bar | FF-27, FF-25 T | `AgeCell.tsx` |
| `StageBar` | A thick progress bar, green / amber / track — *72%*, *24 of 62 · 41 MB left*, *29 of 151 read*, route progress with an amber segment for could-not-read | FF-08, FF-50, RW-05, RW-09 T, RW-26 | `workflow/StageBar.tsx` |
| `Avatar` | Initials in a grey circle — *DO*, *MB*, *MC* — single or stacked on the crew row | FF-09, FF-15, FF-29 T, FF-44 T | none as a component (`AppShell`'s `initialsOf` is the helper) — native-only |

## 3 · Cards, rows and lists — 10

| Component | What the images show | Seen on | Web kit |
|---|---|---|---|
| `Panel` | The card: white, 8 radius, `#d7d3d3` border on the `#f3f2f2` page; a **selected** card has a 2 px dark border | everywhere | `Panel.tsx` |
| `BandHeading` | Small caps heading inside a card or above a list — *TIME*, *ASSET*, *CREW*, *OUTCOME*, *DEBRIEF*, *SIGNATURE*, *THE TEMPLATE EXPECTS*, *ADDED IN THE FIELD*, *TODAY*, *TURNED IN* | FF-15, 23, 34; RW-01 | `BandHeading.tsx` |
| `Kicker` | The brand-orange caps line above a title — *METER EXCHANGE · RESIDENTIAL*, *DISCONNECT — NON-PAYMENT*, *MASTER*; and the sidebar's section words | FF-15, FF-27, FF-20, FF-09 | `Kicker` in `TextBits.tsx` |
| `JobCard` | Status band (pill left, priority right) · customer name · address · *WO-4822 · Meter exchange* · window and distance · an optional missing-part warning · the action row *Start · Navigate · Hold · ⋮* | FF-10, FF-10 T | none — native-only |
| `ListRow` | A tappable row — title, one muted line, a right value or chevron (*1318 Maple Street · 3 meters · stop 12 in walk order · 40 m away*; *Waiting to send · 62 items · 4 batches*; *Skills · Water metering, backflow · 4*) | RW-05, FF-50 T, FF-44 T, RW-01 T | none — native-only (the web lists in `DataTable`; a phone list is not a table) |
| `FactBlock` | Label / value pairs down a card — *Distance 0.2 miles · 2 min*, *Crew North · 4 technicians*, *Gate code 4417*, *Serial MTR-0471 · Model Neptune T-10 · Size 5/8″* | FF-12, FF-44 T, RW-07 T, FF-38 T | `FactBlock.tsx` |
| `KPIStrip` | Figures with a caption, side by side — the **clock tiles** *Travel 14m · 08:00 → 08:14* / *On site 1h 12m · Running since 08:46* (`R9`); the **stat tiles** *8 left today · 3 done · 1 on hold*, *15 meters left · 129 read · 7 could not be*, *Last month 48,210 · Expected 40,000–56,000* | FF-15, FF-63, RW-01, RW-09 | `KPIStrip.tsx` |
| `ModuleTile` | FF-63's two tiles — icon + *Jobs* / *Reads* + *Open →*, a `KPIStrip`, and a *NEXT* / *NEAREST STOP* fact. Shows what is left and what is next, **never how fast anybody is going** (`R120`) | FF-63, FF-63 T | none — native-only |
| `CheckList` | Rows with a state icon and a right value — the turn-in summary (*129 readings taken* ✓), FF-08's load list (done ✓ / in progress ◷ / waiting ○ with *14 of 14*, *8 of 11*, *Waiting*), and the **check rows** of the safety gate (a 48 pt checkbox, green when ticked) and of a done task (green tick, title struck through) | RW-25, FF-08, FF-16, FF-27, FF-17 T | `CheckList.tsx` |
| `TimelineRow` | A coloured left bar by kind (admin grey, travel blue, job green, running amber) · title · time span · duration on the right | FF-47 | none — native-only |

## 4 · Inputs and controls — 9

| Component | What the images show | Seen on | Web kit |
|---|---|---|---|
| `Button` | **Three tiers and two sizes** (T-07): primary filled `#e12e13` (*Start*, *Debrief*, *Claim*, *Sync now*); secondary outlined (*Navigate*, *Hold*, *Cancel*); **danger tier** outlined in danger red (*Disconnect anyway*, *Reopen*, *Turn in 136 of 151*); a dark neutral fill (*Check now*, *Read it*, *Nearest* selected); disabled grey (*Tasks locked*, *Close job*). Full-width 56 pt for the screen's one primary, 48 pt otherwise; icon + label where drawn (*Google Maps*, *Photo*, *Remark*, *Download everything*); **icon-only 48 pt square** for *⋮*, refresh, scan, map, backspace | every screen | `Button.tsx` + `buttonKit.ts` |
| `SubTabs` | Two or three equal tabs with an orange underline — *Today · Tue · Wed*, *Mine · Nearby*, *Signed · Refused*, *Today · Week* | FF-10, FF-33, FF-47, FF-10 T | `SubTabs.tsx` |
| `SegmentedControl` | Two halves, the chosen one filled dark — *Nearest · Walk order* (`R75`: nearest first is the default, the office's walk order one tap away) | RW-05 | `SegmentedControl.tsx` |
| `Switch` | Toggle — *Bigger text · Easier with gloves on*; *Photos on wi-fi only* (2026-10-28; replaced *photos on mobile data*, `R54` SUPERSEDED) | FF-51 | `Switch.tsx` |
| `RadioCard` | Full-width option cards with a circle, the chosen one with a dark border and filled dot — the **four outcomes** *Passed · Partly done · Failed · Waiting on someone* (`R4`); RW-17's eight can't-read reasons (*the list is the utility's own*, `R82`); FF-36's reopen reasons | FF-34, RW-17, FF-36 | none — native-only |
| `Stepper` | *− 1 +* with 56 pt buttons — *"A quantity stepper hit a hundred times with gloves on"* | FF-23 | none — native-only |
| `ReadingField` | The big reading box — value large, unit beside it (*gal*, hard rule 3), a muted line under it (*Expected 40,000–50,000 · last 48,180*); border amber out of range, green in range, never a refusal (`R11`, `R78`, `R80`) | FF-20, RW-09 T | none — native-only (the web shows a value with its unit through `UnitCell`) |
| `NumericKeypad` | 3 × 4 grid of large keys, *Clear*, *0*, backspace — a technician taps, never types (`R38`) | RW-09, RW-09 T | none — native-only |
| `TextField` | Label above, bordered input, help line under it (*Ask the office to reset it*) — the field's **5 / 6 / 20 px anatomy** (T-07) | FF-05, FF-33 | none as one component — the web's anatomy lives in `FormModal` fields and `AffixField`; native-only, same anatomy |

## 5 · Capture and evidence — 4

| Component | What the images show | Seen on | Web kit |
|---|---|---|---|
| `PhotoTile` | A thumbnail with the **burned-in stamp** under it — *20 Oct 2026 · 09:18 · 30.2651, -97.7494 · ±4m · D. Ortiz · WO-4822* (`R94`) — and a caption (*Before*, *After*) | FF-21, FF-20, FF-17 T | none — native-only |
| `DocumentCapture` | The dashed slot with a camera icon — *Take photo*, *Two more*, *Photo, if it helps* — with its requirement chip (*REQUIRED*, *3 PHOTOS · 1 SO FAR* — `R110`, short of the count warns and never blocks). **Camera only for evidence** (`R93`: *"The gallery is never offered"*); camera, file or typed for an asset paper, with the source recorded (`R108`, FF-60) | FF-21, RW-17, FF-17 T, FF-60 | `documents/DocumentCapture.tsx` |
| `SignaturePad` | Dashed pad with a baseline, *Clear*, *Captured by D. Ortiz · 20 Oct 09:58*; the *Refused — record reason* path beside it | FF-33, FF-34 | none — native-only |
| `ScanInput` | The camera view — scan frame with the red line, *Point at the badge or the serial plate*, *TORCH ON · CONTINUOUS* / *CAMERA ONLY* labels, the stamp preview strip; then the matched card (*Matches the record. MTR-0471, Unit 2.*) and *Type it* when it will not read | FF-38 T, RW-11 T, RW-14 T | `workflow/ScanInput.tsx` |

## 6 · States — 3

| Component | What it is | Web kit |
|---|---|---|
| `EmptyList` | An empty list or a zero-result search, with the honest offline limit where it applies (*"Only today's assets are here. A signal searches the whole utility."* — `R42`) | `EmptyList` / `ZeroResults` in `StateFrame.tsx` |
| `Toast` | A short confirmation after an act | `Toast.tsx` (`ToastProvider`, `useToast`) |
| `BuildVersion` | *VERSION 2.587.0 · build 412* at the drawer and sidebar foot (`R40`, T-58; one product version plus the store build number — conflict 4) | `BuildVersion.tsx` |

---

## 7 · Native-only — the 20 the web kit does not have

`BottomBar` · `PaneLayout` · `ContextPane` · `StickyFooter` · `FullScreenAlert` · `MapView` · `SyncChip` · `Avatar` ·
`JobCard` · `ListRow` · `ModuleTile` · `TimelineRow` · `RadioCard` · `Stepper` · `ReadingField` · `NumericKeypad` ·
`TextField` · `PhotoTile` · `SignaturePad` · `Drawer`.

**Rule for a lane adding a component:** look in `07-frontend/src/components/` (and its `README.md`) first. If the
thing exists there, take its name and its props and render natively. If it does not, the native name is the one in
this file. Either way, add the row here in the same commit.

## 8 · What is NOT a component

* **The tablet board-title strip** (*"FF-17 T Tasks"*) — the canvas labelling its board; not product chrome.
* **Any figure drawn in a wireframe** — *11 jobs · 6h 20m*, *$241.38*, *52,410 gal* are illustrations (B14 rule 37);
  a component renders what the server or the handset store gives it.
* **Blue strips that state RATIONALE.** *"One tap downloads the whole day and every route. The old way — Settings,
  then sync — was three taps too many."* (FF-50 T) · *"Two technicians are two time records and the cost is their
  sum. The lead closes it."* (FF-29 T) · *"1D barcodes and 2D QR. Scanning is how you identify a meter; typing is the
  fallback."* (FF-38 T). B14 rule 33 puts **rationale at zero words on screen** — these are the design explaining
  itself to its reader. A `WarningBox` carrying a FACT or an INSTRUCTION within rule 33's caps (*"Needs a signal."*)
  is product; one carrying a reason is not. **Which drawn strips survive is for the lane building each screen to
  decide against rule 33, case by case** — recorded here so nobody builds all of them because they are drawn.
