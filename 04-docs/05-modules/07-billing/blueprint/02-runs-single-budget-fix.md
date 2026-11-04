# Billing blueprint · the per-entry page map for §03 – §08

**What this is.** One row per drawn entry in sections **03 · The bulk bill run, redrawn**,
**04 · Single bills**, **05 · Budget bills**, **06 · Fix a bill**, **07 · Past billing runs**
and **08 · Bill printing** of `05-prototype/04 Billing, As Built.pdf` (249 pages, on the
DEFAULT branch `claude/confirm-understanding-3ktufc`). It records, per entry: the number and
title **as drawn**, the page range, the address line and screen id, the state chips, whether
the entry's own caption marks it **AS-BUILT** or **REDESIGN**, and whether it carries a
`BUILD THIS` band.

**What this is NOT.** It is not a specification, not a diff against the product, and not
evidence that any screen matches any drawing. **Nothing here was measured against running
code and no screen was walked for this file.** Step 1 measures and classifies; it fixes
nothing.

## How it was read — and why the method matters

**Every page in the range was opened AS AN IMAGE with the `Read` tool** (B14 rule 42, PO:
*"When you use images to create screens your accuracy is higher; hence dont create screens
using only Text"*). The text layer of this PDF **drops every slash, colon and digit from the
monospace address line** — `/:tenant/billing · S30 · BIL-01` extracts as
`tenantbilling    S  BIL` — so a screen→page map grepped from the text returns **zero** rows.
The text dump was used only to split the file into pages and to pick candidate pages; every
fact below was read off the rendered PNG.

⚠ **B14 rule 37: every figure drawn in these frames is an ILLUSTRATION, never a value to
build to.** The figures quoted below (`$346,386.55`, `1,251`, `$3,737.00`, …) are quoted as
*what the drawing shows*, so a builder can find the element. **Do not assert one in a test or
seed a fixture from one.**

## The real section boundaries — measured, not assumed

The lane brief estimated "roughly p100 to p180". **That was wrong by a wide margin in both
directions.** Measured page by page:

| § | Title as drawn | Starts | Ends | Pages |
|---|---|---|---|---|
| 03 | The bulk bill run, redrawn | **p28** (lower half; entry 02.5 of §02 ends on p28's top) | p99 (top) | 72 |
| 04 | Single bills | **p99** (lower half) | p118 (top) | 20 |
| 05 | Budget bills | **p118** (top) | p129 (top) | 11 |
| 06 | Fix a bill | **p129** (top) | p146 (top) | 17 |
| 07 | Past billing runs | **p146** (top) | p147 (upper half) | 2 |
| 08 | Bill printing | **p147** (upper half) | p151 | 5 |
| — | §09 *What happened when it was driven* begins | p152 | — | — |

**So the six sections occupy p28–p151, not p100–p180.** A lane that had started at p100 would
have missed the whole of §03 — which is 72 of the 124 pages and every one of the bulk-run
entries.

## §03 · The bulk bill run, redrawn — p28 – p99(top)

> ⚠ **SUPERSEDED FOR THE SCOPE AND CHECK SCREENS 2026-09-30 — BUILD THEM FROM `05-prototype/bulk-bill-run-2026-09-30/` (72 images, `README.md`, `inventory.md`), NOT FROM p46–p50.** The PO reviewed a newer drawing of the same four steps screen by screen and approved it (*"im good with thsi"*, decision log 2026-09-30, *"BULK BILL RUN REDESIGN: BUILD STARTS"*). What moved on `16 Scope`: the **`DEFAULTS` group (standing answers) moves to Check, per problem tag** (BR-BIL-1040 amended — PO: *"ths is correct"*); the **which-services scope is removed** (PO: *"this filter is of now use"*; BR-BIL-1043 superseded for new runs); a **run name** and a required **bill template** are fields; every run-level refusal and warning shows at once, each on its field (BR-BIL-1050), and a gap warns with **no tick** (BR-BIL-1051). `17 Check` becomes category → tag → accounts (changes row 36). The four step names, the step count and this page map are unchanged. Change list: `../14-bulk-bill-run-changes.md`.

**Front matter, p28(lower) – p36(upper)** — not entries: *Six steps become four* · *Where the
engine and the screens disagree* · *Every control on these screens, ruled 2026-09-11* · *the
service badge* · *the pre-bill check that runs between Scope and Check*. No chips, no
addresses, nothing to build from directly.

**Every entry in §03 carries the identical caption**, and it is the caption that classifies
the whole section:

> `REDESIGN` drawn **2026-09-11**, still unbuilt at Version 35 (2026-09-13), drawn to the
> Product Owner's 2026-09-11 run-intent ruling, the 2026-09-11 *per connection* ruling and
> the 2026-09-12 on-screen-calculation ruling. **NEVER BUILT.** Today the product ships a
> **six**-step wizard, screens 04–09 in §17.

**So §03 holds no AS-BUILT drawing at all.** The as-built six-step wizard it replaces is
§17's screens 04–09, outside this lane.

### The five layers of screen 17 — `17.L1` – `17.L5`

Each is *a layer of* screen 17, not a screen; each carries the layer chip plus three
`A LAYER OF SCREEN 17` chips and the address `/:tenant/billing/run`. All five: **REDESIGN,
NEVER BUILT, no `BUILD THIS` band.**

| # | Title | Pages | Address line, as drawn | Chips |
|---|---|---|---|---|
| 17.L1 | Step rail | p36(low) – p37 | `/:tenant/billing/run · screen 17, one layer at a time · 4 steps` | `LAYER ONE` + 3× `A LAYER OF SCREEN 17` |
| 17.L2 | Run state | p38 – p39(top) | `/:tenant/billing/run · 4 cells · GET /billing/runs/{id}` | `LAYER TWO` + 3× |
| 17.L3 | Navigation | p39(mid) – p41(top) | `/:tenant/billing/run · 4 bands · 15 chips · generated, never declared` | `LAYER THREE` + 3× |
| 17.L4 | Selection | p41(mid) – p43 | `/:tenant/billing/run · appears only with a selection` | `LAYER FOUR` + 3× |
| 17.L5 | One row | p44 – p46(upper) | `/:tenant/billing/run · 6 columns · the order never moves` | `LAYER FIVE` + 3× |

### The four numbered steps, and the in-flight state

| # | Title | Pages | Address · screen id | Chips | `BUILD THIS` |
|---|---|---|---|---|---|
| **16** | **Scope** | p46(mid) – p48(top) | `step 1 of 4 — what to bill · /:tenant/billing/run · S31 · BIL-02 · was step 1 of 6` | `STEP ONE` · Blocked `S89` · New build `S38` `S90` `S95` · New read `S46` · Exists behind `S24` `S25` `S26` `S34` | **YES** — *New build · "Two inputs become five groups, and pricing starts here" · CLOSES `BIL-S24` · `BIL-S25` · `DEF-106` · `DEF-1084`* |
| 17.0 | Checking | p49(mid) – p50 | `/:tenant/billing/run · between Scope and Check · stages 1–5, pure · nothing written` | `IN FLIGHT` · New build `S96` · Exists behind `S40` `S41` `S45` | no |
| **17** | **Check** | p51 – p54(top) | `step 2 of 4 · /:tenant/billing/run · replaces steps 2, 3 and 4 of six · BIL-02` | `STEP TWO` · New build `S27` `S83` `S90` `S91` `S92` `S96` · New read `S73` · Exists behind `S26` `S28` `S32` `S40` | **YES** — *New build · "One screen, priced, filterable, decisions inline" · CLOSES `BIL-S26` · `BIL-S27` · `BIL-S28`* |
| 18 | Sign off | p82(mid) – p85(top) | `step 3 of 4 · /:tenant/billing/run · GET /billing/runs/{id}/summary` | `STEP THREE` · New build `S43` `S50` · Exists behind `S29` `S40` | no |
| 19 | Send | p85(mid) – p86(mid) | `step 4 of 4 · /:tenant/billing/run · the bills exist; nothing has been dispatched` | `STEP FOUR` · New build `S50` · Exists behind `S30` | no |

⚠ **Entry `18.1` does not exist and its absence is deliberate**, stated on p84: *"This screen
and `18.1 The numbers` were the same screen twice — one summary and one granular version of
it. Two drawings of one screen is the confusion this document was restructured to remove, so
the granular one won and the old summary is not kept alongside it. **There is one screen 18.**"*

### The nine case chips — `17.1` – `17.9`

All nine share the address shape `step 2 chip · N rows · <engine case> · /:tenant/billing/run
· step 2, one chip · BIL-02 · engine case <name>`, and all nine are **REDESIGN / NEVER BUILT
with no `BUILD THIS` band.** Seven of the nine carry exactly `Exists behind S32 S33 S47`.

| # | Title | Pages | Kind chip | Work chips | Rows drawn · engine case |
|---|---|---|---|---|---|
| 17.1 | No read | p56(mid) – p57(mid) | `THREE WAYS` | New build `S91` `S92` · Exists behind `S32` `S33` `S47` `S49` | 4 · `missing_read` |
| 17.2 | Unusually large | p57(low) – p59(top) | `COMPARISON` | Exists behind `S32` `S33` `S47` | 3 · high usage |
| 17.3 | Unusually small | p59(mid) – p60(mid) | `QUIET HALF` | Exists behind `S32` `S33` `S47` | 1 |
| 17.4 | Zero use | p60(mid) – p61(mid) | `BASE BILLS` | Exists behind `S32` `S33` `S47` | 1 |
| 17.5 | Unusual days | p61(low) – p62(mid) | `UNPRICED` | Exists behind `S32` `S33` `S47` | 1 |
| 17.6 | Meter changed | p62(low) – p64(top) | `TWO SPANS` | Exists behind `S32` `S33` `S47` | 1 |
| 17.7 | Multiplier | p64(mid) – p65(top) | `TENFOLD` | Exists behind `S32` `S33` `S47` | 1 |
| 17.8 | Estimated | p65(mid) – p66(mid) | `DEFAULTED` | Exists behind `S32` `S33` `S47` | 44 |
| 17.9 | Base only | p66(low) – p67(mid) | `TWO CAUSES` | Exists behind `S32` `S33` `S47` | 31 |

**The chip inventory is a finding, not a list.** p41: *"A case kind the engine did not raise
**gets no chip**… The as-built screen declares fifteen."* Nine are drawn because nine are
what the engine emits; the seven that cannot occur are not drawn, and that is the point of
the merge (p87).

### Held, blocked and ready — `17.10` – `17.15`

| # | Title | Pages | Kind chip | Work chips | Address detail |
|---|---|---|---|---|---|
| 17.10 | Held now | p67(low) – p69(top) | `YOUR DEFAULTS` | Exists behind `S32` `S47` | `step 2 chip · 15 rows · one exclusion row each · BIL-02` |
| 17.11 | Account fix | p69(mid) – p70(mid) | `UPSTREAM` | New build `S39` · Exists behind `S32` `S34` `S47` | `3 rows · stage resolve-subscription · break stage resolve-subscription` |
| 17.12 | Read fix | p70(low) – p72(top) | `PART RETRY` | Exists behind `S32` `S47` | `2 rows · stage measure-consumption · break stage measure-consumption` |
| 17.13 | Rates fix | p72(mid) – p73(top) | `MANY ACCOUNTS` | Exists behind `S32` `S47` | `1 row · stage price-usage · break stage price-usage` |
| 17.14 | Ready | p73(mid) – p74(mid) | `SKIM ONLY` | Exists behind `S32` `S34` `S47` | `1,251 rows · nothing raised · nothing raised, nothing to decide` |
| 17.15 | Masters | p74(low) – p76(top) | `CROSS-CUTTING` | New build `S39` · Exists behind `S32` `S34` `S47` | `step 2 VIEW · 11 rows · cuts across every band` |

All six: **REDESIGN / NEVER BUILT, no `BUILD THIS` band.** `17.15` is drawn as a **view**
rather than a band — p75: *"A master can be ready, held or blocked — it is not a state, it is
a shape of account."*

### The bulk actions — `17.16` – `17.20`

Address shape `step 2 bulk · … · /:tenant/billing/run · a bulk action, confirmed · BIL-02`.
All five **REDESIGN / NEVER BUILT, no `BUILD THIS` band.**

| # | Title | Pages | Kind chip | Work chips | Selection drawn |
|---|---|---|---|---|---|
| 17.16 | Estimate all | p76 – p77(top) | `BEFORE AFTER` | New build `S42` · Exists behind `S47` `S48` `S49` | 4 selected, 3 will change |
| 17.17 | Hold these | p77(mid) – p78(mid) | `TAKES REASON` | New build `S42` · Exists behind `S47` `S48` | 3 selected · **danger tier** |
| 17.18 | Accept | p78(low) – p79(mid) | `NO CHANGE` | New build `S42` · Exists behind `S47` `S48` | 2 selected · the total does not move |
| 17.19 | Confirm factor | p79(low) – p81(top) | `WHO WHEN` | New build `S42` · Exists behind `S47` `S48` | 1 selected |
| 17.20 | Waiver | p81(mid) – p82(top) | `REFUSED` | New build `S42` `S77` `S102` · Exists behind `S47` `S48` | refused — one account at a time |

⚠ `17.20` carries a self-flagged hazard on the drawing itself: *"**The case may never appear.**
The engine **does not currently raise a late-fee case at all** — it is declared and never
emitted. So this screen may be reachable only after that is fixed. It is drawn now because
the refusal is law either way."*

### Arrears and apply-all — `17.21` – `17.22`

⚠ **These two do NOT sit with the other bulk actions.** They are drawn **after** `18 Sign off`
and `19 Send`, separated from `17.20` by the carry-over table. A lane looking for them
between `17.20` and `18` will not find them.

| # | Title | Pages | Kind chip | Work chips | Address |
|---|---|---|---|---|---|
| 17.21 | In arrears | p88(low) – p90(mid) | `NEW CHIP` | New build `S44` · Exists behind `S47` | `/:tenant/billing/run · a new chip in Everything else · 312 rows · measured against 09/11/2026` |
| 17.22 | Apply all | p90(mid) – p91(mid) | `AT SCALE` | New build `S42` · Exists behind `S47` `S48` `S49` | `/:tenant/billing/run · a chip-wide bulk action · the 25,000-account case` |

Both **REDESIGN / NEVER BUILT, no `BUILD THIS` band.**

### The carry-over table, and the two narrative blocks

| Ref | Title | Pages | Chips | Kind |
|---|---|---|---|---|
| `03 · carry-over` | **Nothing the six steps did is lost in the four** | p86(low) – p88(mid) | `No commitment` · 3× `EVIDENCE, NOT WORK` | Not a screen. One row per element across all six original steps: **38 elements → 19 unchanged · 9 moved · 4 relabelled · 5 removed**, and the four-step total **47 = 38 − 5 + 14 new**. |
| — | *Units or accounts — and what screens 1 and 2 must say* | p91(low) – p94(mid) | — | Narrative. Mints `BIL-S38` and `BIL-S39`. |
| — | *What the rulings cost to build* | p94(mid) | — | Narrative. |

### Held accounts — `20`, `20.1` – `20.3`

| # | Title | Pages | Address · screen id | Chips | `BUILD THIS` |
|---|---|---|---|---|---|
| 20 | Held queue | p94(low) – p96(top) | `47 rows · /:tenant/billing/pending · exists, and cannot be acted on · BIL-08` | `NO EXIT` · New build `S39` `S44` · Exists behind `S35` `S36` `S100` | no |
| 20.1 | Catch up | p96 – p97(top) | `the catch-up · /:tenant/billing/pending · endpoint served, control absent` | `OLD PERIOD` · Exists behind `S35` | no |
| 20.2 | Hold one | p97(mid) – p98(top) | `a standing hold · /:tenant/billing/pending/hold · does not exist in any form` | `RULING OWED` · **Blocked `S37`** | no |
| 20.3 | Release | p98(mid) – p99(top) | `the release · /:tenant/billing/pending/release · does not exist in any form` | `AUDIT TRAIL` · **Blocked `S37`** | no |

All four **REDESIGN / NEVER BUILT.** `20.2` and `20.3` are the only `Blocked` entries in §03
besides `16 Scope`'s `S89`, and `20.2` states what it is blocked on in its own rule table:
*"**What we need from you** — Whether a standing hold may exist at all, and whether a review
date is **required** as drawn or merely offered."*

### §03 · counts

| | |
|---|---|
| Entries drawn | **31** (5 layers + 4 steps + 1 in-flight + 22 chips/actions/queue entries) — `16`, `17`, `17.0`, `17.L1`–`17.L5`, `17.1`–`17.22`, `18`, `19`, `20`, `20.1`–`20.3` |
| REDESIGN | **31 of 31** |
| AS-BUILT | **0** |
| Carrying a `BUILD THIS` band | **2** — `16 Scope` and `17 Check` |
| Carrying `Blocked` | **3** — `16` (`S89`), `20.2` (`S37`), `20.3` (`S37`) |
| Non-entry blocks in the range | 3 — the carry-over table, *Units or accounts*, *What the rulings cost to build* |
| Screen ids seen | `BIL-02` (the run wizard), `BIL-08` (the held queue), `S31` |
| Pages I could not read | **0** of 72 |

## §04 · Single bills — p99(lower) – p118(top)

**Front matter, p99(lower) – p101(mid)** — *what belongs here and what does not* (a cut bill
and a disconnect charge are raised automatically from the disconnect screen, not here) ·
*one rail, six kinds* · *step 2 keeps the same lettered spine on all six kinds* — **A** where ·
**B** what · **C** readings · **D** how it prices · **E** the money · **F** the customer's
other accounts.

**Every entry in §04 carries the identical caption:**

> `REDESIGN` drawn **2026-09-12**, still unbuilt at Version 35 (2026-09-13), drawn to
> `BR-BIL-013`'s deposit-first order and the 2026-09-12 content ruling. **NEVER BUILT.**
> Today the product ships the *One-time bill* tab, **screen 11 in §17**.

**No entry in §04 carries a `BUILD THIS` band.** No entry carries a screen id — the address
line is `One-time bill · step N of 3 · …` with no `S##` and no `BIL-nn`.

| # | Title | Pages | Address line, as drawn | Chips |
|---|---|---|---|---|
| 21 | Who and when | p101(mid) – p102(mid) | `One-time bill · step 1 of 3 · all six kinds` | `STEP ONE` · New build `S82` · Exists behind `S51` `S54` |
| 22.1 | Interim | p102(low) – p104(mid) | `One-time bill · step 2 of 3 · drafts as interim` | `STEP TWO · MID-CYCLE` · New build `S82` · Exists behind `S51` `S54` `S55` |
| 22.2 | First bill | p104(low) – p106(mid) | `One-time bill · step 2 of 3 · drafts as first` | `STEP TWO · DERIVED` · Exists behind `S51` `S54` `S55` |
| **22.3** | **Final bill** | p106(low) – p109(top) | `One-time bill · step 2 of 3 · drafts as final` | `STEP TWO · DEPOSIT FIRST` · **Blocked `S56`** · Exists behind `S51` `S54` `S55` `S57` |
| 22.4 | Back-bill | p109 – p111(top) | `One-time bill · step 2 of 3 · drafts as back-bill` | `STEP TWO · TAKES A LIST` · Exists behind `S51` `S52` `S54` `S55` |
| 22.5 | Penalty | p111(mid) – p112(mid) | `One-time bill · step 2 of 3 · drafts as penalty` | `STEP TWO · A REASON` · New build `S77` `S102` · Exists behind `S51` `S52` `S54` |
| 22.6 | Fee | p112(low) – p114(mid) | `One-time bill · step 2 of 3 · drafts as fee` | `STEP TWO · A CODE` · Exists behind `S51` `S54` |
| 23 | Confirm and send | p114(mid) – p116(mid) | `One-time bill · step 3 of 3 · all six kinds` | `STEP THREE` · **Blocked `S56`** · Exists behind `S51` `S57` |
| 24 | Periods | p116(low) – p118(top) | `One-time bill · from step 2 of a back-bill or a penalty` | `THE LIST BUILDER` · Exists behind `S52` `S55` |

**§04 counts: 9 entries · 9 REDESIGN · 0 AS-BUILT · 0 `BUILD THIS` · 2 `Blocked` (`22.3`,
`23`, both on `S56`) · 0 pages unreadable.**

## §05 · Budget bills — p118(top) – p129(top)

**Front matter, p118 – p121(mid)** — *budget bills run inside the regular cycle, and must not
run separately* (PO 2026-09-12, *"There is no separate budget run"*) · *the three money
columns and why they are never collapsed into one* · *when a customer asks for it from the
portal* · *two prototype controls that are named here instead of drawn*.

**Every entry in §05 carries the identical caption:**

> `REDESIGN` drawn **2026-09-12**, still unbuilt at Version 35 (2026-09-13), drawn to the
> Product Owner's 2026-09-12 ruling that budget bills run inside the regular cycle.
> **NEVER BUILT.** Today the product ships the *Budget Bills* tab, **screen 12 in §17**.

**No entry in §05 carries a `BUILD THIS` band; none carries a screen id.**

| # | Title | Pages | Address line, as drawn | Chips |
|---|---|---|---|---|
| 25 | Budget bills | p121(mid) – p122(mid) | `Billing › Budget Bills · the tab exists; this is the table it needs` | `THE LEVEL, THREE WAYS` · **Blocked `S75`** · New build `S80` `S81` `S82` · New read `S74` · Exists behind `S58` `S59` `S67` |
| 25.1 | Enrol | p122(mid) – p124(mid) | `Billing › Budget Bills · from + Enrol an account, or from an ask on screen 25.3` | `ONE AT A TIME` · **Blocked `S75`** · New build `S80` `S82` · New read `S74` · Exists behind `S58` `S59` `S67` |
| 25.2 | Settle-up forecast | p124(low) – p126(top) | `Billing › Budget Bills · a forecast; the cycle run does the posting` | `READ ONLY` · New build `S80` · Exists behind `S60` |
| 25.3 | Asks | p126(mid) – p127(mid) | `Billing › Budget Bills · service requests raised from the portal` | `THE CUSTOMER ASKS, A CLERK ENROLS` · Exists behind `S66` `S67` |
| 25.4 | Portal · Level pay | p127(mid) – p129(top) | `Customer portal · /level-pay and /level-pay/standing` | `THE CUSTOMER'S SIDE` · Exists behind `S66` |

⚠ **`25.2` records its own withdrawn control, and the reason is the thing to keep:**
*"This screen was drawn with a button, and the button was wrong. An earlier version of this
drawing offered `Settle these 2`. **The cycle run already posts the settle-up**, on the
account's own bill, inside the same write that creates it, **idempotently per invoice**. A
bulk button would have been a second writer for the same money — corrected here rather than
quietly removed, because the reasoning is the thing worth keeping."*

⚠ **`25.4` is the only customer-portal entry in this lane**, and it is the dead-control case
`CLAUDE.md` hard-won law 2 names: *"the join control is **held**… Across **64 portal routes**,
both level-pay endpoints are `GET`. So a customer can see exactly what they would pay, press
`Join level pay`, **and nothing happens**. That is the dead-control failure, on a money
screen, with an open question against it."*

**§05 counts: 5 entries · 5 REDESIGN · 0 AS-BUILT · 0 `BUILD THIS` · 2 `Blocked` (`25`,
`25.1`, both on `S75`) · 0 pages unreadable.**

## §06 · Fix a bill — p129(top) – p145(lower)

**Front matter, p129 – p132(mid)** — *four steps, and step 2 changes with the correction* (PO
2026-09-12, *"we will ahve to make it wizard - 4 steps"*) · *what each case shows and what it
deliberately does not* · *the thirteen, and what each one does* · *five things people bring
that are not corrections* · *what a correction does to the books — confirmed* ·
*cancelling bills and regenerating them*.

**The thirteen reasons, in three classes, as the document tabulates them (p130):**

| Class | Count | The reasons | What happens | Balance moves by |
|---|---|---|---|---|
| **R** | 7 | Wrong read · Wrong rate or plan · Wrong tax · A charge was missed · A charge was billed in error · Wrong period or service · Theft, restated | Credits the original **in full** and issues a rebill for the right amount | The difference |
| **C** | 1 | Goodwill | A goodwill credit **on the account, tax excluded**. The bill is not touched | The credit, later |
| **D** | 5 | Customer name · Service or mailing address · Premises or unit label · Meter number or read dates · Template or language | Reprints the document with the details corrected | Exactly **$0.00** |

Three rules sit above that table: a multi-reason case takes the strongest class present,
**R > C > D**; **a D-class case with a non-zero money delta is refused**; and a correction
applies only to the **latest bill in its chain**, walked to a depth of twenty.

**Every entry in §06 carries the identical caption:**

> `REDESIGN` drawn **2026-09-12**, still unbuilt at Version 35 (2026-09-13), drawn to the
> Product Owner's 2026-09-12 four-step wizard ruling and the same day's confirmation that
> approval moves the books. **NEVER BUILT.** Today the product ships the *Fix a bill* tab,
> **screen 13 in §17**.

**No entry in §06 carries a `BUILD THIS` band; none carries a screen id.**

| # | Title | Pages | Address line, as drawn | Chips |
|---|---|---|---|---|
| 26 | What and why | p132(mid) – p134(mid) | `Billing › Fix a bill · step 1 of 4` | `STEP ONE` · **Blocked `S61`** · New build `S80` `S81` `S83` · Exists behind `S62` |
| 26.1 | One bill | p134(mid) – p135(mid) | `Billing › Fix a bill · step 2 of 4` | `STEP TWO · CLASS R` · **Blocked `S61`** · New build `S80` `S83` |
| 26.2 | Several months | p135(low) – p136(mid) | `Billing › Fix a bill · step 2 of 4 · one account, a window` | `STEP TWO · CLASS R` · **Blocked `S61`** · New build `S80` · Exists behind `S69` |
| 26.3 | A batch | p136(low) – p138(mid) | `Billing › Fix a bill · step 2 of 4 · many accounts, one case` | `STEP TWO · CLASS R` · **Blocked `S61`** |
| 26.4 | Goodwill | p138(mid) – p139(mid) | `Billing › Fix a bill · step 2 of 4 · the bill is right` | `STEP TWO · CLASS C` · Exists behind `S62` |
| 26.5 | The page only | p139(low) – p140(mid) | `Billing › Fix a bill · step 2 of 4 · the page is wrong` | `STEP TWO · CLASS D` · Exists behind `S63` |
| 26.6 | What it changes | p140(low) – p142(mid) | `Billing › Fix a bill · step 3 of 4 · one bill` | `STEP THREE` · Exists behind `S68` |
| 26.7 | What it changes · many | p142(mid) – p144(mid) | `Billing › Fix a bill · step 3 of 4 · several months, or a batch` | `STEP THREE` · Exists behind `S68` `S69` |
| 26.8 | Generate and send | p144(mid) – p145(mid) | `Billing › Fix a bill · step 4 of 4 · all three classes` | `STEP FOUR` · New build `S85` |

**§06 counts: 9 entries · 9 REDESIGN · 0 AS-BUILT · 0 `BUILD THIS` · 4 `Blocked` (`26`,
`26.1`, `26.2`, `26.3`, all on `S61`) · 0 pages unreadable.**

## §07 · Past billing runs — p145(lower) – p147(upper)

**Front matter, p145(lower).** *"One table, and it is nearly free. `GET /billing/runs` is
served, `PastRunsPanel` is written and wired into the wizard, and the actor column is
populated and on the wire — so the blocker this screen names on itself (`"nothing would list
it"` / `"no actor column"`) is **false in both halves that matter**. This is commitment
`BIL-S1` drawn as a table with filters."*

| # | Title | Pages | Address line, as drawn | Chips | Caption |
|---|---|---|---|---|---|
| 27 | Past runs | p146 – p147(upper) | `Billing › Past billing runs · GET /billing/runs` | `ALREADY SERVED` · New build `S76` · Exists behind `S1` | `REDESIGN` drawn **2026-09-12**, drawn to `BR-BIL-065` and the run-history read that already exists. **NEVER BUILT.** Today the product ships a grey panel reading *"It arrives with the billing run work"* — **screen 10 in §17** |

**No `BUILD THIS` band; no screen id on the address line.**

**§07 counts: 1 entry · 1 REDESIGN · 0 AS-BUILT · 0 `BUILD THIS` · 0 `Blocked` · 0 pages
unreadable.**

## §08 · Bill printing — p147(upper) – p151(mid)

**Front matter, p147 – p148(mid)** — *what it costs, measured rather than estimated*
(per bill **0.012 s** · pages per bill **6** · ceiling **25,000 bills**) · *what comes out*
(`bills/` · `manifest.csv` · `held-back.csv` · `README.txt`) · *and it changes no address*.

**Both entries carry the identical caption:**

> `REDESIGN` drawn **2026-09-12**, still unbuilt at Version 35 (2026-09-13), drawn to the
> Product Owner's 2026-09-12 ruling making Print bills a Billing tab. **NEVER BUILT.**
> Today the product ships the *Print bills* screen, **screen 15 in §17**.

| # | Title | Pages | Address line, as drawn | Chips |
|---|---|---|---|---|
| 28 | Print bills | p148(mid) – p150(top) | `Billing › Print bills · the seventh tab` | `A TAB, A TABLE, A BUTTON` · New build `S93` · Exists behind `S64` `S65` `S70` |
| 28.1 | Held back | p150(mid) – p151(mid) | ``Billing › Print bills · from See the 8 held back · also held-back.csv`` | `EIGHT NAMED REASONS` · Exists behind `S65` `S70` |

**No `BUILD THIS` band on either; no screen id on either address line.**

`28.1`'s eight reasons are the code's own, and **three of them are billing defects rather
than clerk work**: Address incomplete · Address unreadable · **No bill number** · **Unsafe
bill number** · **Duplicate filename** · Document refused · Original unreadable · Page count
unknown. *"Every held bill carries exactly one, so the reason column can never be blank."*

**§08 counts: 2 entries · 2 REDESIGN · 0 AS-BUILT · 0 `BUILD THIS` · 0 `Blocked` · 0 pages
unreadable.**

## The whole lane, in counts

| | §03 | §04 | §05 | §06 | §07 | §08 | **Total** |
|---|---|---|---|---|---|---|---|
| Pages | 72 | 20 | 11 | 17 | 2 | 5 | **124** (p28–p151) |
| Entries drawn | 31 | 9 | 5 | 9 | 1 | 2 | **57** |
| **REDESIGN** | 31 | 9 | 5 | 9 | 1 | 2 | **57** |
| **AS-BUILT** | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| `BUILD THIS` bands | **2** | 0 | 0 | 0 | 0 | 0 | **2** |
| Entries carrying `Blocked` | 3 | 2 | 2 | 4 | 0 | 0 | **11** |
| Pages I could not read | 0 | 0 | 0 | 0 | 0 | 0 | **0** |

**Every page in p28–p151 was opened as an image — 124 of 124.** p27 and p152 were opened as
well, to fix the §02/§03 and §08/§09 boundaries.

⚠ **THERE IS NOT ONE AS-BUILT DRAWING IN THIS WHOLE RANGE.** Sections 03–08 are **57
redesigns, none of them ever built**, and each one names the screen it replaces in §17
(`04`–`09`, `10`, `11`, `12`, `13`, `15`). **So no measurement of the product against any
drawing in this lane can be a drift finding** — the only lawful comparison is *does the
product do what §17's as-built drawing shows*, and §17 is outside this lane.

### `BUILD THIS` — two more than the document's own reconciliation names

The `BUILD THIS` band appears **exactly twice** in p28–p151 — on **`16 Scope`** (p46) and
**`17 Check`** (p51). Verified twice, by two independent methods: read off the rendered PNG,
and counted in the text layer (the words are letters only, so extraction does not drop them).

⚠ **The blueprint index's framing does not mention these two.** `00-index.md` records the
document's own p6 reconciliation — *"Drawings to build: **11**, across **nine screens** —
01, 02.1, 02.2, 02.3 (two states), 02.4 (two states), 02.5, 10, 13, 14"* — and every id in
that list is a §02 entry. **Counted across the whole document the band occurs 12 times:** ten
in §02's page range (p6, 7, 11, 15, 17, 21, 22, 24, 25, 27) and **two in §03** (p46, p51).
**I am not settling that** — §02 belongs to a sibling lane and the reconciliation may be
counting drawings rather than bands. **What is measured and certain: §03 carries two
`BUILD THIS` bands, and §04–§08 carry none.**

## Money-path findings — quoted on both sides, nothing decided

⛔ **Step 1 decides nothing here. None of the following is a build item and none of it has
been measured against running code.** Each is recorded so the coordinator can route it.

### 1 · No drawing in this lane shows an edit on an issued bill — and one says so explicitly

This was the thing my lane was told to hunt for. **It is not there, and the document is
emphatic in the opposite direction.** `26.1`'s rule table (p135):

> **Nothing is edited, and that is structural** — An issued bill takes **no update and no
> delete** — the database refuses it, so a correction is always two new documents. **Which is
> also why the prototype's *edit specific line items* control cannot be ported.**

Against `CLAUDE.md` hard rule 4: *"no UPDATE/DELETE on issued invoices, invoice lines,
payments, journal entries — corrections are new rows."* **These agree.** The same agreement
is restated at `17.18` (*"Accepting a reading does not change it… an issued bill is never
edited"*), at `26.8` (*"After this there is no undo. A posted entry cannot be un-posted and a
sent document cannot be un-sent. The remedy is a **new correction over exactly these
bills**"*) and at `28.1` (*"It links out; it does not edit… **Billing may not write another
module's record**"*).

**`26.5` class D is the one worth reading twice, and it is also clean.** It changes what a
document says while `$0.00` moves — and the drawing states the original is untouched:

> **The original** — *Still exists, and is still what was first sent* · **A later reprint** —
> *Renders the corrected one* · **A second fix later** — *Builds on this one — fixes
> accumulate* · **It reads master data; it does not write it.**

**The open end, stated not decided:** a reissue *"becomes the document the customer is
entitled to, and reissues **accumulate** — each is composed from the one before rather than
the original"*. **Nothing in these pages names where that chain of reissued documents is
stored.** That is an absence to verify against `B2` before anyone builds `26.5`, not a rule
conflict.

### 2 · `22.3 Final bill` — a signed B4 figure is quoted, and an unsigned money behaviour sits beside it

**The frozen figure, quoted by the drawing as already signed** (p108):

> **Deposit-first is frozen law, not a layout choice** — A **$150.00** deposit held 14 months
> at 2% earns **$3.50**, so **$153.50** applies *before* any path is chosen — **finance-signed**.

**Nothing here moves a ❄️ FROZEN B4/B5 figure**, so this is not a STOP. ⚠ **But under B14
rule 37 it is still an ILLUSTRATION on a drawing: do not assert `$3.50` in a test or seed a
fixture from it.** Whether B4 carries this exact worked example is a check against B4 itself,
which this lane did not make.

**Beside it, the drawing declares an unsigned money behaviour in its own words** (p108):

> ⚠ **The sibling panel is unsigned, and is kept out of the arithmetic** — A sibling **debt**
> seizes a refund; a sibling **credit** is **shown and never applied**. **Neither is signed**
> — both are prototype behaviour with an open question — and where a dispute and a sibling
> debt collide **the dispute wins**, because the dispute hold IS signed.

**This already has a register row and must not be re-asked (hard-won law 13).**
`12-governance/01-open-questions.md:457` — **`OQ-362`**, status **OPEN — non-blocking**:
*"A CREDIT ON ANOTHER OF THE SAME CUSTOMER'S ACCOUNTS IS SHOWN AND NEVER APPLIED, WHILE A
DEBT ON ONE IS SEIZED — WHICH HALF IS THE PRODUCT?"* **The drawing and the register agree.**

### 3 · `22.3` — "there is no settlements table", and hard rule 7

The drawing states an absence on a money path (p108):

> ⚠ **Nothing records which path was chosen** — The engine computes the settlement and hands
> it back; **there is no settlements table**. So *"exactly one settlement path per final
> bill"* is enforced inside a single call and **not across calls** — a clerk can settle the
> same account twice, and the chosen path has nowhere to live.

Against `CLAUDE.md` hard rule 7: *"Every money action writes `audit_log`."* **Grepped:
`"settlements table"` returns 0 rows in `01-open-questions.md` and 0 in `02-decision-log.md`.**
⚠ **I have NOT verified the absence against the code** — step 1's own rule is that a grep
returning nothing proves the grep was wrong, not that the thing is absent, and the drawing is
a 2026-09-11 reading of `2.235.0` against today's `2.261.4`. **Verify on the endpoint before
anyone states this absence anywhere else.**

### 4 · `26 What and why` — the reason→class map is unratified, and it decides whether a credit note issues

p134, the drawing's own rule row:

> ⚠ **The reason map is proposed, not ratified** — It waits on one sentence: *"a misspelt name
> changes $0.00 and issues no credit note; a wrong rate changes $19.92 and always issues a
> credit note plus a corrected bill."* And **a tenant's own reason is refused rather than
> defaulted**, because the lookup that would class it is not built.

**Thirteen reasons map to three classes, and the class decides whether the ledger moves.**
Grepped: `"reason map"` returns **0** rows in both registers. This is the sharpest unrecorded
item in my lane — **it is a money behaviour that the document itself marks unratified and
that exists in no register row.** Routing is the coordinator's; I mint nothing.

### 5 · `17.20 Waiver` — a screen drawn for a case the engine never raises

p81, on the drawing:

> ⚠ **The case may never appear.** The engine **does not currently raise a late-fee case at
> all** — it is declared and never emitted. So this screen may be reachable only after that is
> fixed. It is drawn now because the refusal is law either way.

Restated at `26.6` (p142): *"⚠ **The late-fee row is a stated absence** — Nothing assesses a
late fee today — the function **has no production caller at all**."*

That is `CLAUDE.md` hard-won law 2 (*built is not wired*) asserted about the billing engine in
two places. ⚠ **UNVERIFIED HERE.** I did not run the code and I did not read the engine, so I
have filed no defect — filing one on a stale document's claim would be exactly the false
report step 1's own brief warns about. **Someone must grep for the late-fee case's emitter
before this is recorded as anything.**

### 6 · `20.2` / `20.3` — held accounts, `Blocked S37`, and a ruling that is genuinely owed

`20.2 Hold one` and `20.3 Release` both address `/:tenant/billing/pending/hold` and
`/…/release` and both say *"does not exist in any form"*. `20.2`'s rule table names what it
waits on:

> **What we need from you** — Whether a standing hold may exist at all, and whether a review
> date is **required** as drawn or merely offered.

Grepped: `"standing hold"` returns **0** rows in `01-open-questions.md` and **0** in
`02-decision-log.md`. Like item 4, it is a `Blocked` chip with no register row behind it.

### 7 · Two internal inconsistencies in §08, recorded so nobody "fixes" the wrong one

p147 says *"the strip is seven wide on every drawing in **§02 and §04–§08**"*; p149's rule
table says *"The strip is seven wide on every drawing in **§02 and §04–§07**"*. **Same
document, two pages apart, two different ranges.** Neither is a rule; both describe the tab
strip. Recorded, not resolved.

## What this record does NOT establish

* **No screen was walked.** Nothing here was compared against the running product, in either
  direction. The `Exists behind` / `New build` / `New read` / `Blocked` chips are **the
  document's claims about a 2026-09-11 reading of `2.235.0`**, and today is `2.261.4` — 26
  versions on. Every one of them is a hypothesis to re-check.
* **No absence was verified on an endpoint.** Items 3 and 5 above are the document's claims,
  quoted as claims.
* **No id was allocated and no defect was filed.** Nothing in this lane met the bar: every
  candidate is either already registered (`OQ-362`) or rests on an unverified claim in a
  stale document.
* **Every figure quoted is an illustration** (B14 rule 37) — `$346,386.55`, `1,251`,
  `$4,206.55`, `$153.50`, `$25.00`, `$99.24`, `+$4,593.80`, `404 + 8 = 412`, `0.012 s`,
  `25,000 bills` and the rest. **None may be asserted in a test or seeded into a fixture.**
