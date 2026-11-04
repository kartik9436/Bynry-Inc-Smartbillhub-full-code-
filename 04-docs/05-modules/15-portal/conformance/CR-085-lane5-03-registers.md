# CR-085 lane 5 · THE REGISTERS — defects re-verified, CPB-01..24, the 12 unratified rules, B14 rule 39

Measured 2026-09-11 against tip `b4063d1e6`, version **2.235.0**. Method and its one
limitation are stated at the top of `CR-085-lane5-02-deltas.md`.

---

# 1 · The open / partially-fixed `DEF-CWP` rows in this lane's slice, re-opened

The register holds **274 `DEF-CWP` rows, 89 of which are not closed** — 76 `open`, 6
`partially-fixed`, 1 `closed`, plus 3 duplicate / 3 invalid / 1 wontfix. **43 of the 82
open-or-partially-fixed rows name a bill, a document, a dispute or a comparison in their
title or surface**; the 17 that are actually about this lane's six screens are below.
`13-wireframe-delta.md` and `14-layout-audit.md` are dated 2026-09-05 and say *"before
citing a row here as current, open the screen"* — each row below was opened.

| row | status in register | what the screen says on 2026-09-11 |
|---|---|---|
| `DEF-CWP-4000` [D1] 28 signed-in screens carry no head | partially-fixed | **Half true still.** `CWP-027`, `CWP-029`, `CWP-030`, `CWP-031` and `CWP-055` all carry kicker + h1 + action row. **`CWP-028` carries one on the happy path and NONE on its failed or loading branch** — filed as **`DEF-CWP-4859`** |
| `DEF-CWP-3986` [D11] six named components never built, incl. `DocumentPreview` | partially-fixed | **`DocumentPreview` is BUILT and WIRED** (`<object … ?view=1>`, 605×783 at 1280) — that line is done. `BillHistoryBars` (the `YOUR LAST 12 BILLS` strip on `CWP-030`) is **still absent** |
| `DEF-CWP-3945` a pinned help answer never reaches the bill screen | partially-fixed | **Placed.** `BillDetail.tsx` renders `AttachedAnswerCard` from `bill.attached_answer` with `Read the whole answer →`. Not exercised here (the fixture pins none), so the row's own half about the clerk's end is untested by this walk |
| `DEF-CWP-3943` 36 catalogue keys render to nobody, 22 of them the portal's | partially-fixed | **Still true, and there is one more**: `portal.bills.payHeld` in all eleven catalogues with no consumer — **`DEF-CWP-4861`** |
| `DEF-CWP-3988` [D13] ten drawn screens have no address | partially-fixed | not this slice — all six of mine are routed and all six render their own `data-screen` id |
| `DEF-CWP-4202` a customer queries a bill without being shown what it is for | open | **Partly repaired.** `CWP-055` now reads *"You are querying bill BL-2608-000042, $191.00"* — the amount is there. The month, the period and the services are not, and the drawing heads the page *"About your August bill, $191.00"* |
| `DEF-CWP-4206` the against-last-August panel is empty on every bill | open | **Server-side; not reproducible from the client.** Given correct labels the component drew `Aug 2025` / `Aug 2026` and the series correctly. Stays against `billing_seam.bill_comparison_for` |
| `DEF-CWP-4207` the comparison and its endpoint still document the breakdown as UNBUILT | open | **Still true.** `components_available:false`, `components_blocked_by:"OQ-CWP-1563"`, and the screen prints *"We are still working out how to show you the reasons line by line."* |
| `DEF-CWP-4209` both year-on-year bars labelled `Aug` | open | **Server-side**, as above — the client renders `this_year_label` / `last_year_label` verbatim |
| `DEF-CWP-4210` every component share drawn in ink where a rise should be brand red | open | **Cannot be judged** — no component shares are served at all (`DEF-CWP-4207`), so the colour rule has nothing to colour. It is blocked behind 4207, not independent |
| `DEF-CWP-4211` the heading is the generic question, not the answer | open | **Still true.** h1 reads `Why is this bill different?` where the drawing reads `Why August costs $14.80 more than July` |
| `DEF-CWP-4212` never says whether the RATE changed | open | **Still true.** No `Your prices did not change between these two bills.` and no `PRICES DID CHANGE` line |
| `DEF-CWP-4213` explains a bill and offers no way to act on it | open | **Still true.** The only control on `CWP-030` is the back link |
| `DEF-CWP-4657` the bill PDF answers 500 when the kept file is gone | open | **Looks FIXED and the row is stale.** `bill_document_pdf` raises named `BizError`s for both absences (`portal.billDocument.notKept` / `portal.document.notTrusted`) and cites `DEF-CWP-4699`. Returned to its owner to re-read rather than closed here |
| `DEF-CWP-4712` DisputeBill left an unused variable, a second eslint error | open | **Looks FIXED and the row is stale.** The file's own comment records the removal (*"A first draft kept a `billFailed` flag beside this and never read it — eslint said so, correctly"*) and only `bill` remains |
| `DEF-CWP-4711` G107 red on four portal screens, unreported | open | not re-run here; named so the next lane does not assume it was covered |
| `DEF-CWP-4678` the budget-billing chart overflows 390 by 25px | open | not this slice (`CWP-066`); named because the same `w-[…]` shape is the cause of **`DEF-CWP-4865`** on `CWP-029` |

## The audits' agreed root cause — *"no list on the shared table"* — VERIFIED

Both 2026-09-05 passes agreed on three root causes and the prompt flagged this one as
probably mine. **On this lane's two list screens it is FIXED.** `CWP-027` and `CWP-031` both
render `PortalListTable`: search box, filter chips, sortable headers (`⇅` on every sortable
column), row icons and a pagination footer, and `CWP-027` additionally becomes a card list
below 768px. The residue is not the table — it is `Rows per page 50 / 100 / 200 / 500 /
1000`, a staff-vocabulary control on a consumer screen that neither drawing has, and
`CWP-031` keeping a six-column table at 390 where its sibling became cards.

## Filed by this lane

`DEF-CWP-4859` · `DEF-CWP-4860` · `DEF-CWP-4861` · `DEF-CWP-4862` · `DEF-CWP-4863` ·
`DEF-CWP-4864` · `DEF-CWP-4865`.

---

# 2 · The 24 specifications — which touch these six screens

`CPB-08`, `CPB-13`, `CPB-14`, `CPB-15`, `CPB-19`, `CPB-20`, `CPB-23` and `CPB-24` name a
screen in this lane; `CPB-03`, `CPB-17` and `CPB-01` reach it. Every one reads `UNVERIFIED`
in the blueprint's own register; the middle column is this lane's answer, which is what that
register asks engineering to fill in.

| spec | screens | built? | evidence |
|---|---|---|---|
| **CPB-03** a customer can download what we sent them | **60**, 43 | **PART-BUILT on 60** | `Download a year ↓` is on `CWP-031` and is **not held** — the *"Downloads are not ready yet"* sentence does not render. It IS held, correctly, when there is nothing kept: `Nothing kept to download yet`. The *spreadsheet* half is `CPB-15` and is absent |
| **CPB-08** a usage month says what it cost | 50, **32** | **NOT BUILT on 32** | see §3 below — this straddles lane 8 |
| **CPB-13** a disputed amount is split out on the request | **34**, 56 | **NOT BUILT** | `CWP-055` says the opposite of the drawing: `The bill stands and its due date keeps running` where the drawing says `The disputed amount is not due and no late fee is added to it`. No money travels with a request, exactly as the spec states |
| **CPB-14** a customer can ask for a proof-of-service letter | **60** | **NOT BUILT** | no `ASK FOR A LETTER` rail, no `Ask for one` control, nothing on the phone frame either |
| **CPB-15** Documents says how long we keep things, and exports | **60** | **NOT BUILT, both halves** | the sub-line carries no `6 documents · kept for seven years`; there is no `Download a spreadsheet` |
| **CPB-19** Documents can reach the record of what we sent | **60** | **NOT BUILT — and the refusal is live** | `portal.documents.queueUnavailable` renders in full when `documents: null`. 33 words over three sentences, against B14 rule 32's one-sentence budget |
| **CPB-20** delivery is confirmed, not just dispatch | **60** | **NOT BUILT — and the refusal is live** | the `What we know` column reads `SENT`, and a banner reads *"We cannot confirm that anything arrived — post and email remain the record of delivery."* |
| **CPB-23** every screen carries its How-you-get-here row | **all** | **the DOORS are built; the ROW is not** | every one of the six has at least one live inbound anchor: frame nav → `/bills`; `/bills` rows → `/bills/:n` and `/bills/:n/document`; `/bills` `WhereNext` → `/documents`; `/bills/:n` → `/comparison`, `/document`, `/dispute`. ⚠ **One door is width-dependent** — the list's print icon is inside the desktop table only (`DEF-CWP-4864`) |
| **CPB-24** the two dead hold sentences are retired | 1, 3 | **not this slice — and it is one short.** `portal.bills.payHeld` is a third of exactly the same kind, on `CWP-027` (`DEF-CWP-4861`). The spec should be widened from two named keys to the rule |
| **CPB-17** a signed-out visitor at a signed-in address is offered a sign-in | 53, 54 | **NOT BUILT — and it is live on all six of mine** | each answers `401` on `/portal/session` and renders `Failed / We could not open this page. / You're signed out. Sign in again to continue. / Retry / Download error report / Cancel`, with **no sign-in link**. The spec names two screens; it is true of every signed-in screen, which the spec itself says |
| **CPB-01** a customer can pay by card | 35, 36, 37, 6, 8 | not this slice | the `Pay` control on `CWP-027` and `CWP-028` sends to `/pay-now`, where the refusal lives — correct placement |
| CPB-02, 04, 05, 06, 07, 09, 10, 11, 12, 16, 18, 21, 22 | — | **do not touch these six screens** | |

## 3 · `CPB-08` — what MY side needs

> *"Nothing joins a usage month to the bill line it produced. Screens: 50 · 32. DONE LOOKS
> LIKE: The Usage screen reads '800 kWh at $0.1150 = $92.00' for August, and the figure is
> the bill's own line, not a re-calculation."*

Lane 8 owns screen 50. **Screen 32 — `/bills/:number/comparison` — is mine, and my side is
the other end of the same join.** Three things, in order:

1. **The server must serve the attribution.** `GET /portal/bills/{n}/comparison` today sends
   `components: []`, `components_available: false`, `components_blocked_by: "OQ-CWP-1563"`.
   Until that question is answered nothing on this screen can move — it is `DEF-CWP-4207`'s
   real blocker and it is an **open question, not a missing component**.
2. **Every component must be the BILL'S OWN LINE, not a recomputation** — the same
   requirement as lane 8's. `PortalBillComponent` already carries `amount_display`, so the
   figure can be the server's rounded one; the type is right and nothing fills it.
3. **The parts must sum exactly to the headline, and a remainder must be shown as
   *everything else*, never hidden** — the drawing's own rule, and the reason the screen
   cannot simply list the biggest three.

**What my side does NOT need from lane 8:** the usage series. `against_last_year` already
arrives and already renders. The join CPB-08 names runs one way for me — from a bill LINE to
a month — and the other way for lane 8.

**One request to lane 8:** whatever wording is agreed for *"800 kWh at $0.1150 = $92.00"* on
screen 50 should be the same sentence on screen 32, because a customer who reads both and
finds two phrasings of one fact will ring about it. The catalogue keys today are
`portal.billDetail.ratePerUnit` (`{{rate}} / {{unit}}`) on my side and
`portal.usage.*` on theirs — two vocabularies for one figure.

---

# 4 · The 12 unratified drawn rules — which these screens depend on

The blueprint's appendix A marks 12 of its 24 rules **`NO HOME` — stated only here**. They
are **proposals, not law**. Seven of the twelve bear on this lane; the two the prompt named
both bite, and both are already breached.

| rule | as stated | how these six screens stand |
|---|---|---|
| **R-06** | *"Never ask a customer to compute — show the difference, not two numbers."* | `CWP-030` **gives the difference AND both numbers** (`Last month … $176.20` / `This bill … $191.00` / `Difference +$14.80`), and the heading is the question rather than the answer. `CWP-027` shows `Amount` and `Owing` as two columns — which is signed law (`BR-CWP-043`) and would **collide with R-06 if R-06 were ratified.** That collision is why R-06 needs a ruling rather than adoption |
| **R-10** | *"Bad news never appears without the way out beside it."* **"the strongest rule on the page"** | **Breached in four measured places.** `CWP-027` FAILED: *We could not read your bills.* with no retry and no phone number (the drawing asks for both). `CWP-028` FAILED: one sentence, no head, no back link. `CWP-031` FAILED: *Please try again.* with nothing to press. Signed-out at all six: *Sign in again to continue* with no sign-in link. **Where it is HONOURED:** `CWP-029` NOT-AVAILABLE offers `Ask us for a copy →`, and `CWP-031`'s year download is refused with a reason |
| **R-05** | *"Amount due and due date appear in the same place on every screen."* | the frame carries `$191.00 due Aug 22` on every signed-in screen (lane 1's). Within mine, `CWP-028` shows `Due 08/22/2026` and `CWP-027` shows `DUE IN 9 DAYS` — **two vocabularies for one fact** |
| **R-07** | *"One filled button per screen."* | `CWP-027` has one outline `Pay`; `CWP-028` one `Pay` in the card; `CWP-055` one `Check it`; `CWP-029` one download anchor. Consistent, though `Pay` is outline where the pack draws it filled |
| **R-19** | *"The portal is a second channel; every bill is printed regardless."* | `CWP-029`'s whole existence depends on it and it holds — the screen serves the KEPT file and never re-renders (`BR-CWP-045`) |
| **R-22** | *"Three states — loading, empty, failed — can never render as the same picture."* | **Breached on `CWP-027` and `CWP-028`**: all three are one `Card` with one grey sentence. The drawing asks for a skeleton on loading |
| **R-23** | *"No sentence states a fact it does not derive."* | held on the figures — `CWP-028` sums nothing, `CWP-027` reads `owing` rather than subtracting. **Breached in one place**: `Came back to us on .` states a bounce the data does not support (`DEF-CWP-4860`) |

Also inherited rather than unratified, and relevant: **R-01** (*every icon carries its word*)
is breached by the row actions on `CWP-027` and `CWP-031` — `aria-label` and `title` only —
and the blueprint gives the reason (*a phone has no hover*). **R-16** (*money … never four on
screen*) is contradicted by section 05's own MONEY note; see `02-deltas.md` §2.

---

# 5 · B14 rule 39, ratified 2026-09-11 — measured on this lane's screens

Rule 39 says of itself that it is **entirely unbuilt at ratification** and that no `--sp-N`
token exists. These are the figures, not a complaint. All `getComputedStyle` /
`getBoundingClientRect` on the running app at 1280.

## The anchor that is this lane's — **th/td 8×12**

| | measured | verdict |
|---|---|---|
| `td`, columns 1..n−1 | `8px / 12px / 8px / 12px` | **✅ exactly 8×12** on all six tables (bills, documents, three charge tables, readings) |
| `th`, same columns | `0px / 12px / 8px / 12px` | **❌ vertical is 0 top, 8 bottom** — not 8 |
| first cell of every row | `padding-left: 0` | edge-flush, deliberate; last cell `padding-right: 0` likewise |

## The other anchors these screens touch

| anchor | ratified | measured | |
|---|---|---|---|
| page | `24 / 16 / 32` | `24 / 20 / 24 / 20` on all six, both widths | ❌ sides 20, bottom 24 |
| title | `40 / 800` | `40px / 800` | ✅ |
| `.input` | `6×10`, `min-height 36` | `8px / 12px`, `min-height: auto`, heights 38 / 65 / 41 | ❌ |
| field → field | `20px` | **16px** (`flex flex-col gap-1` wrappers, 16px between) | ❌ |
| label → input | `5px` | **4px** | ❌ |
| input → helper | `6px` | **13px**, and the helper is a sibling `<p>` with no `aria-describedby` | ❌ — **`DEF-CWP-4863`** |

⚠ **The helper gap is the one rule 39 explains itself by**: at 4px above and 13px below, the
helper reads as attached to the NEXT field rather than to its own input, which is the failure
the ruling names in its own words.

## Ad-hoc values — rule 39 bans `3 / 7 / 9 / 14` outright

Every occurrence on these six screens, with its element:

| value | element | screens |
|---|---|---|
| `padding-top/bottom: 7px` | the filter-chip buttons — `All` `Unpaid` `This year` `Bills` `Receipts` `Letters` — class `… px-3 py-[7px] …` | `CWP-027`, `CWP-031` |
| `padding-left/right: 9px` | `.pill` status chips — `DUE IN 9 DAYS`, `PAID`, `SENT` | `CWP-027`, `CWP-031` |
| `margin-top/bottom: 13px` | every un-margined `<p class="text-base …">` — the bill number under a card month, `$107.50 for this service`, `Both taken by a reader…`, `A sentence or two is plenty.` | all six |
| `margin-top/bottom: 15px` | every un-margined `<p class="text-body …">` — the period line, `Due 08/22/2026`, `You are querying bill …`, `Tell us and somebody will look at this bill.` | all six |

⚠ **The 13 and 15 are not typed anywhere.** `--text-base` is `13px` and `--text-body` is
`15px`, and a `<p>` with no margin utility takes the user-agent's `1em` — so the font size
becomes the margin. **That is the single largest source of off-scale spacing in this lane**,
it is invisible in source, and it is exactly the PO's complaint that produced rule 39
(*"the components are too much close as well as manage the margins also"*). A `<p>` reset, or
a margin utility on every paragraph, fixes it in one place; `py-[7px]` and the pill's `9px`
are two edits.

## Money, hard rule 2

Every TOTAL on all six screens displays at 2 dp — `$191.00`, `$176.20`, `$168.94`, `$0.00`,
`$14.80`, `$107.50`, `$47.50`, `$36.00`. **Unit RATES display at 4 dp** — `$0.1150 / kWh`,
`$4.2400 / kgal`, `$6.8900 / kgal`, `$5.0000 / kgal` — which section 05's MONEY note asks
for by name and which appendix rule R-16 forbids by name. Reported, not resolved.
