# §03 element inventory — the whole bulk bill run, read as images

`CR-105-BRC03` · wave 1 · 2026-09-14 · **no code was written in this wave**

**What this is.** One row per element for **all of section 03** of
`05-prototype/04 Billing, As Built.pdf` — *"The bulk bill run, redrawn"*. An element is
anything a clerk can see or touch: a heading, a field, a chip, a count, a column, a button,
a refusal, a stated absence, a progress band, an empty state.

**Why it exists.** Four PO corrections landed on 2026-09-14 and every one had the same
cause: a brief written from PART of §03. `p049`/`p050` — the in-flight Check frames, where
the whole architecture of the screen lives — had never been opened. The PO's verdict was
*"still you have made maany issues in Bill run."*

**A later wave builds from this file and from nothing else.**

---

## 0 · Provenance, and how this was read

| | |
|---|---|
| Source | `05-prototype/04 Billing, As Built.pdf` — **14,363,163 bytes**, sha256 `137a2a48c0398c39897f49aafa0bbb9c44ff21d6258eed78cd7558e6cc200971` |
| Method | **Every page rendered to PNG and read AS AN IMAGE** (B14 rule 42), `10-scripts/pdf/pdf_render.py` at scale 2.0, with 6× crops where type was small |
| Text layer | Used only as an INDEX and to confirm exact wording. ⚠ **The text layer drops every digit in the mono meta lines** — the subset font's CMap does not decode them — so `4 bands · 15 chips` extracts as `bands   chips`. Any count taken from `pdf_text.py` in this section is missing. |
| Pages read | **p027 – p099**, i.e. §03 plus one page either side to fix the boundary |

### The section boundary, settled

**§03 runs from mid-`p028` to mid-`p099`.** It shares its first page with §02 (entry `02.5
Bill detail · Sent` occupies the top of p028's spread on p027) and its last page with §04
(`04 Single bills` starts at mid-p099). The brief's range `p028–p099` is **correct**; what
it does not say is that both end pages are shared.

### The frame question, settled for the whole section

**There is no AS-BUILT drawing anywhere in §03.** Counted strictly over p028–p099:
**36 `REDESIGN` bands, 0 `AS-BUILT` bands** — and there are exactly **36 drawings**, so
every one is a redesign. Every one also carries the identical banner:

> `REDESIGN` drawn **2026-09-11** (17.21, 17.22, 20–20.3 and 18–19 the same; 18, 19, 20.x
> re-dated where noted), still unbuilt at Version 35 (2026-09-13), drawn to the Product
> Owner's 2026-09-11 run-intent ruling, the 2026-09-11 *per connection* ruling and the
> 2026-09-12 on-screen-calculation ruling. **NEVER BUILT.** Today the product ships a
> **six**-step wizard, screens 04–09 in §17.

So the **Frame** column below reads `REDESIGN` on every row and the **In the product?**
column reads `no — NEVER BUILT` on every drawn element unless it says otherwise. The
as-built screens each entry replaces are named per entry as `Exists behind S##`.

### The four reading rules this inventory applies

1. **The annotation beats the drawing.** A drawn box is an illustration (B14 rule 37).
   Where the two disagree the annotation is recorded as the specification and the drawing
   is recorded as the illustration — and the disagreement is filed (§9).
2. **Every drawn number is an illustration.** `9,412`, `$2,361,904`, `RUN-0002`, `CY-001`,
   `1,284`, `$346,386.55` are EXAMPLES. They are recorded so the arithmetic can be checked;
   none is a value to build to.
3. **Counts must tie out.** Every sum in this file is reproduced (§2, §3). A group whose
   numbers do not sum has been misread — or is a defect, and §9 says which.
4. **The drawing's stage numbers are ONE BEHIND the code from stage 5 on** (`DEF-BIL-5269`).
   Verified against `06-backend/apps/billing/pipeline.py`:

   | Drawn (p033) | Code `SEQUENCE` | |
   |---|---|---|
   | 1 resolve-subscription | 1 resolve-subscription | |
   | 2 measure-consumption | 2 measure-consumption | |
   | 3 price-usage | 3 price-usage | 🔒 rating |
   | 4 apply-charges | 4 apply-charges | 🔒 rating |
   | — *(no drawn stage)* | **5 apply-discounts** | inserted 2026-08-22, `DEF-502` |
   | 5 compute-tax | 6 compute-tax | 🔒 rating |
   | 6 assemble-document | 7 assemble-document | mints the bill number |
   | 7 post-to-ledger | 8 post-to-ledger | `TERMINAL_STAGES = (7, 8)` |

   The drawing says *"stages 1–5 are pure"*; the code says *"Stages 1–6 are the pure
   front"*. **Same boundary, different number.** Every stage citation below gives both.

---

## 1 · Page map of §03

| Pages | Entry | What is on them |
|---|---|---|
| p028–p029 | §03 opener | PO intent verbatim · six steps become four · the twelve engine/screen disagreements |
| p030–p032 | control law | the 2026-09-11 control ruling · the eleven service badges · every input audited |
| p033–p034 | the pre-bill check | the seven/eight stages · what changes · the 137 ms cost model |
| p035–p036 | screen 16 in ASCII | zone sketch of Scope · the rules it obeys |
| p036–p045 | **17.L1 – 17.L5** | the five layers of screen 17, each drawn once at full strength |
| p046–p048 | **16 Scope** | STEP ONE, the drawing + six numbered callouts |
| p049–p050 | **17.0 Checking** | **IN FLIGHT** — five KPI tiles, progress band, *"about 35 minutes left"* |
| p051–p053 | **17 Check** | STEP TWO, **settled** — the four-cell KPI strip and the full 26-tag strip |
| p053–p055 | chip taxonomy | the nine engine cases · the three not on the list · the 15-chip inventory |
| p056–p075 | **17.1 – 17.15** | one frame per chip |
| p076–p081 | **17.16 – 17.20** | the five bulk confirms, the last of them a refusal |
| p082–p084 | **18 Sign off** | STEP THREE, five groups |
| p085–p086 | **19 Send** | STEP FOUR, three groups |
| p086–p088 | **carry-over map** | *"Nothing the six steps did is lost in the four"* |
| p088–p091 | **17.21, 17.22** | In arrears · Apply all (the 25,000-account case) |
| p091–p094 | units vs accounts | the master asymmetry and the two 2026-09-11 rulings, worked |
| p094–p098 | **20 – 20.3** | Held queue · Catch up · Hold one · Release |
| p099 | tail | 20.3's annotation, then the red *"one removal needs your ruling"* band |

---

## 2 · The three count sets, and every tie-out

The document states (p041) that it carries **three count sets** and that each reconciles.
All three are reproduced here. **Every figure is an illustration (rule 2).**

### Set A — the settled 1,284-account run (17, 17.L1–L5, 17.1–17.20, 18, 19)

```
READY TO BILL   1,251   $342,180.00
NEEDS YOU          12   $4,206.55 at stake
HELD               21   15 by a default · 6 blocked
RUN TOTAL               $346,386.55   updates as you decide

1,251 + 12 + 21 = 1,284 accounts in scope            ✅
$342,180.00 + $4,206.55 = $346,386.55                ✅
```

### Set B — the in-flight 25,000-account run (17.0, p049–p050)

```
CHECKED SO FAR  9,412   of 25,000
WOULD BILL              $2,361,904   so far
NEEDS YOU          87   $31,204 at stake
HELD SO FAR       141   by your defaults
BLOCKED SO FAR     38   a fix elsewhere

Ready 9,184 + Needs you 87 + Held 141 = 9,412        ✅ = CHECKED SO FAR
```

### Set C — the chip-wide bulk action at scale (17.22, p090)

```
Estimated and billed      198
Actioned, and held         33
Already decided by hand     0
Actioned in total         231                        ✅ 198 + 33 + 0 = 231

RUN TOTAL NOW  $6,284,102.40
THIS ACTION ADDS  + $11,842.60
AFTER          $6,295,945.00                         ✅
```

### Every other sum in §03, checked

| Where | Sum | Result |
|---|---|---|
| p034 cost model | 137 ms × 1,284 / 10,000 / 25,000 / 40,000 = ~3 / ~23 / ~57 / ~91 min | ✅ |
| p058 17.2 | 31 ÷ 7.4 = 4.19 → *"4.2×"* · 64 ÷ 28.0 = 2.29 → *"2.3×"* · 112 ÷ 49.5 = 2.26 → *"2.3×"* | ✅ |
| p059 17.3 | 0.6 ÷ 19.2 = 3.1% → *"3% of its usual"* | ✅ |
| p063 17.6 | 4.1 + 5.8 = 9.9 kgal | ✅ |
| p065 17.7 | 820 × 10 = 8,200 · $191.40 × 10 = $1,914.00 | ✅ |
| p066 17.8 | (7.9 + 8.4 + 8.3) ÷ 3 = 8.2 kgal | ✅ |
| p076 17.16 | $51.30 + $34.80 + $38.60 = $124.70 · $346,386.55 + $124.70 = $346,511.25 | ✅ |
| p077 17.17 | $2,410.75 + $1,284.40 + $41.85 = $3,737.00 · $346,386.55 − $3,737.00 = $342,649.55 | ✅ |
| p075 17.15 | 2 × $12.00 + 2 × $20.00 = $64.00 · $69.60 + $0.57 = $70.17 | ✅ |
| p082 18 grp 1 | 1,273 + 11 = 1,284 · 1,251 + 9 = 1,260 · 1,260 + 24 = 1,284 | ✅ |
| p083 18 grp 3 | $345,672.15 − $4,182.00 = $341,490.15 | ✅ |
| p083 18 grp 4 | $128,402.55 − $96,318.20 = $32,084.35 · + $341,490.15 = $373,574.50 | ✅ |
| p083 18 grp 5 | 18 + 6 + 0 = 24 unbilled | ✅ |
| p084 18 | 6.2 kgal × $4.10 = $25.42 | ✅ |
| p086 19 grp 3 | 412 + 31 + 817 = 1,260 · $112,840.55 + $8,204.10 + $220,445.50 = $341,490.15 | ✅ **ties Send to Sign off** |
| p088 carry-over | rows: 20 + 10 + 3 + 5 = **38** | ✅ (the summary block's 19/9/4/5 = 37 ✗ — §6) |
| p091 17.22 | 198 × 137 ms ≈ 27 s → *"about thirty seconds"* | ✅ |
| p093 per-connection | 2 × ($12.00 + 100 × $0.20) = $64.00 · pooled $12.00 + 200 × $0.20 = $52.00 | ✅ |
| p094 per-connection | 2.00% of $28.50 = $0.57 · 2.00% of $69.60 = $1.39 | ✅ |
| p095 screen 20 | 31 + 16 = 47 · 28 + 13 + 6 = 47 · six reasons = 47 · **38 + 9 + 2 = 49 ✗** | ⚠ `DEF-BIL-5274` |
| p095 screen 20 | 07/02 → 09/11 = 71 days · 08/03 → 09/11 = 39 days | ✅ |
| p066 17.8 footer | *"Showing 50 of 44"* | ✗ `DEF-BIL-5279` |
| p097 20.2 | ~$318 × 3 cycles ≈ ~$955 | ✅ |

---

## 3 · The band strip — **26 tags in 7 bands**, in BOTH frames

One generated component; the same twenty-six on every frame (p040, p041). Both frames are
transcribed; **`Frame A` is the settled 1,284-run, `Frame B` the in-flight 25,000-run.**

| # | Band | Chip (drawn label) | A | B | Tie-out |
|---|---|---|---|---|---|
| 1 | **Needs you** | Missing read | 4 | 31 | |
| 2 | | Unusually large | 3 | 22 | |
| 3 | | Unusually small | 1 | 9 | |
| 4 | | No usage | 1 | 12 | |
| 5 | | Unusual days | 1 | 6 | |
| 6 | | Meter changed | 1 | 4 | |
| 7 | | Multiplier changed | 1 | 3 | **A: 4+3+1+1+1+1+1 = 12** · **B: 31+22+9+12+6+4+3 = 87** ✅ |
| 8 | **Answered by your default** | Estimated | 44 | 322 | |
| 9 | | Base charge only | 31 | 204 | *(no band total drawn)* |
| 10 | **Held** | Never calculated | 15 | 103 | |
| 11 | | Calculated and broke | 6 | 38 | **A: 15+6 = 21** · **B: 103+38 = 141** ✅ |
| 12 | ↳ **WHERE THE FIX IS** | The account or the plan | 3 | 21 | |
| 13 | | The read | 2 | 12 | |
| 14 | | The rates | 1 | 5 | **A: 3+2+1 = 6** · **B: 21+12+5 = 38** ✅ *= calculated-and-broke* |
| 15 | ↳ **THE REASON** | Master coverage | 1 | 6 | |
| 16 | | City limits not recorded | 1 | 9 | |
| 17 | | No base charge for this type | 1 | 6 | |
| 18 | | Cart count missing | 1 | 7 | |
| 19 | | Reading disputed | 1 | 5 | |
| 20 | | No rate version in force | 1 | 5 | **A: 6×1 = 6** · **B: 6+9+6+7+5+5 = 38** ✅ *= calculated-and-broke* |
| 21 | ↳ **HOW LONG IT HAS WAITED** | Under 14 days | 10 | 128 | |
| 22 | | Escalated | 9 | 11 | |
| 23 | | Over 60 days | 2 | 2 | **A: 10+9+2 = 21** · **B: 128+11+2 = 141** ✅ *= the band* |
| 24 | **Everything else** | Ready | 1,251 | 9,184 | |
| 25 | | Masters | 11 | 7 | |
| 26 | | In arrears | 312 | 2,104 | |

**7 bands · 26 tags · 14 top-level + 12 indented.** The partition rule (p040):
*never-calculated + broke = the band · the three stages = broke · the six reasons = broke ·
the three age bands = the band.* **Frames A and B both obey it in full.** Screen 20 does
not — `DEF-BIL-5274`.

⚠ **Two things about this strip a builder must have, and both are contradictions (§9):**
* Entry 17.L3's own meta line reads **`4 bands · 15 chips · generated, never declared`** —
  a third count, verified by a 6× crop of p039. Its annotation and its drawing say seven
  and twenty-six. `DEF-BIL-5272`.
* p041 and p046 both say *"the tags under **Needs you · 12** sum to **more** than twelve, on
  purpose"* — twelve accounts raise **nineteen** case rows. **Both drawn frames sum to
  exactly the band.** `DEF-BIL-5273`. **The rule is the specification: a tag counts CASES,
  a band counts ACCOUNTS, and the built strip must not assert equality.**

---

## 4 · The 15-chip inventory (p054–p055) — the DRILL-IN list, not a second strip

This is the second taxonomy. It is **not** the band strip: it is the list of chips that own
a `17.x` screen, which is why it has 15 rows and 22 screens exist. Transcribed in full.

| # | Chip (this table's label) | Also called | Engine case | Band (this table) | Screen |
|---|---|---|---|---|---|
| 1 | Missing read | No read · unread meter | `missing_read` | Needs you | 17.1 |
| 2 | Unusually large | High consumption | `high_usage` | Needs you | 17.2 |
| 3 | Unusually small | Low consumption | `low_usage` | Needs you | 17.3 |
| 4 | No usage | Zero consumption | `no_usage` | Needs you | 17.4 |
| 5 | Unusual days | Day threshold | `days_threshold` | Needs you | 17.5 |
| 6 | Meter changed | Meter swap · replacement mid-cycle | `replacement` | Needs you | 17.6 |
| 7 | Multiplier changed | Meter factor · CT ratio | `meter_factor` | Needs you | 17.7 |
| 8 | Estimated | Estimated read | `estimated_read` | By your default | 17.8 |
| 9 | Base charge only | Standing charge only · unmetered · vacation hold | `base_only_billing` | By your default | 17.9 |
| 10 | By a default | Held by my own default | — one exclusion row each | Held | 17.10 |
| 11 | **Fix** the account or the plan | Blocked · subscription problem | break stage `resolve-subscription` | Held | 17.11 |
| 12 | **Fix** the read | Blocked · no usable quantity | break stage `measure-consumption` | Held | 17.12 |
| 13 | **Fix** the rates | Blocked · pricing problem | break stage `price-usage` | Held | 17.13 |
| 14 | Ready | Clean · nothing raised | — | Everything else | 17.14 |
| 15 | Masters | Master accounts · HOA · landlord bills | a view, not a case | Everything else | 17.15 |

⚠ **Three places this table disagrees with the drawn strip, and the strip wins**
(p040 states the correction explicitly — *"the words now match the held queue exactly — **the
read**, not *fix the read*"*):

| This table | The drawn strip and the held queue | Build |
|---|---|---|
| `Fix the account or the plan` · `Fix the read` · `Fix the rates` | `The account or the plan` · `The read` · `The rates` | **without the verb** |
| `By a default` (row 10) | `Never calculated` | **`Never calculated`**, with `Calculated and broke` as its pair |
| Everything else = **two** chips | **three** — Ready, Masters, **In arrears** | **three**; `In arrears` is a NEW chip, entry 17.21, and has no row here |

### The nine engine cases against the categories the PO named (p054)

| # | PO's category | Engine case | Verdict as drawn | Screen |
|---|---|---|---|---|
| 1 | High consumption | `high_usage` | Emitted — carries meter, this period, trailing average, ratio and your threshold | 17.2 |
| 2 | Low consumption | `low_usage` | Emitted, same five facts | 17.3 |
| 3 | Zero consumption | `no_usage` | Emitted — and a zero read is not a missing one | 17.4 |
| 4 | Day threshold | `days_threshold` | Emitted — carries meter and days | 17.5 |
| 5 | Plan & rates missing | `no_charge_applies_to_this_customer_type` + five siblings | **A break, not a case** — blocked, fix named, correctly offers no retry | 17.13, 17.11 |
| 6 | Prorated bills | — | **No case kind exists.** Nothing detects a part period as such; the two prorate choices that exist are recorded and unpriced | 17.5, 17.6 |
| 7 | Late payment | `late_fee`, `past_due` | **Declared and never emitted** | 17.20, drawn as the refusal |
| 8 | Credit applied | `true_up` | Declared, not emitted as a case. A Credits view shows exceptions only | — |
| 9 | Not billed in last 3 months | — | **No case kind exists** — *"most valuable"*; screen 20 is the nearest thing | 20 |

**Three the engine emits that were not on the list, and they are drawn:** `estimated_read`
(17.8) · `meter_factor`, the multiplier changed (17.7) · `replacement`, the meter changed
mid-cycle (17.6).

---

## 5 · THE ELEMENT INVENTORY

`REDESIGN` and `no — NEVER BUILT` are the default for every row; the **In the product?**
column carries only what differs from that or what the document says about the as-built
screen. `Stage` gives **drawn / code**.

### 5.0 · Section-level elements (p028–p035)

| Page | Frame | Entry | Element | Drawn value | Kind | Chip | Stage | In the product? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| p028 | — | §03 | Section title | `The bulk bill run, redrawn` | label | — | — | n/a | |
| p028 | — | §03 | Section standfirst | *"Six steps become four, pricing moves to the front, and one screen shows a clerk every account with real money on it before they sign anything."* | fact | — | — | n/a | |
| p028 | — | §03 | PO intent, verbatim | *"our idea is to show all the data to billing clark before submitting the bill run - it kind of allow him to do all decision before hand, see the data correct the data and then submit it so that billing errors are reduce sbtantially"* | fact | — | — | n/a | **The ruling the whole section is drawn to**, 2026-09-11 |
| p028 | — | §03 | Six→four table | 1 Cycle → **KEEP, WIDENED** → 16 · 2 What was found + 3 The customers → **MERGE INTO ONE** → 17 · 4 The totals · 5 Sign off → **KEEP, TRIMMED** → 18 · 6 Send → **KEEP, ONE DOOR ADDED** → 19 | fact | — | — | differs — six today | `DEF-BIL-5247` |
| p029 | — | §03 | What the merge costs | Steps 6→4 · screens 6→4 · sub-tabs 6→**0** · screens where money is visible 1→**3** · screens where a decision is made 1→**2** | count | — | — | differs | sub-tabs become filter chips with counts |
| p029–p030 | — | §03 | *"Where the engine and the screens disagree"* | **TWELVE** rows — 7 are the screen promising more than the engine delivers, 4 the engine delivering more than the screen shows, 1 a wrong reason reaching a clerk (**7+4+1 = 12** ✅) | fact | — | — | n/a | full list below |
| p030 | — | §03 | Control ruling, verbatim | *"all dates should be date picker, all drop down should be drop down, all search should be search and multi select, with all as option available"* | fact | — | — | partial | 2026-09-11 |
| p030 | — | §03 | The six control rules | date → date picker *(already law)* · options → dropdown, **past ten searchable, under five segmented** *(already law)* · multiple choice → chips *(kit landed 2026-09-10)* · **a filter MULTI-selects — NEW, changes a signed rule** · a service is a 20px badge *(law 2026-08-21, applied 2026-09-12)* · **All is the absence of a filter** *(half there)* | instruction | — | — | differs | |
| p031 | — | §03 | Service badge map | E Electric `#ec3013` · W Water `#1e6b8f` · G Gas `#c47a1d` · S Sewer `#5a5555` · T Trash `#3a6b3d` · B Broadband `#6b3d8a` · St Storm water `#2f4a7a` · So Solar `#7a9a2a` · Th Thermal/Heat `#a8256b` · Ba Battery `#3aa39b` · **F Fire `#8f1f14`** | label | — | — | differs | PO: *"we will use Utility Service Chip E, W, G"*; `name[0]` is wrong on six of eleven. ⚠ the table's ORDER puts Broadband 6th; the platform seed has it 8th |
| p032 | — | §03 | Every input audited | 16: cycle `Monthly · Sep 2026` · period/bill/due date pickers · **services are not a control at all → read-only chips with unit counts** · defaults per case, each option stating whether it bills or holds. 17: case filter six flat chips → banded chips with counts and money · service filter not offered → chips, multi-select, All · decision per row a native select (deliberate, ~180px). 20: *as of* fixed to today → date picker · resolved checkbox → dropdown · **origin, stage, reason, cycle, age have NO FILTERS AT ALL** → all five multi-select | control | — | — | differs | |
| p033 | — | §03 | PO ruling, verbatim | *"between step 1 and step 2 - we are basically running pre bill checks and it is not actual bill generation"* | fact | — | — | n/a | the reason 17.0 exists |
| p033 | — | §03 | The stage table | **seven** named stages in one fixed order (see §0 rule 4) | fact | — | 1–7 / 1–8 | differs — **eight** in code | `DEF-BIL-5269` |
| p033 | — | §03 | Purity boundary | *"Stages 1 to 5 are pure and they produce the money. Stage 6 is where a bill comes into existence."* | fact | — | 5 / 6 | matches code | code: `TERMINAL_STAGES = (7, 8)`, *"Stages 1–6 are the pure front"* |
| p033 | — | §03 | Bill-number ruling, verbatim | *"if not use thats okay we will lose it; its okay; dont over complicate"* | fact | — | 6 / 7 | n/a | an unused bill number is lost by ruling |
| p034 | — | §03 | TODAY vs the pre-bill check | what exists when Check opens: **1,251 draft bills, numbered → nothing, figures only** · re-pricing: re-drafts and burns a block of numbers → re-checks, no number touched · honest framing: *"here are the bills"* → *"here is what we would bill"* · bills created: before anybody approved → **at sign-off** | fact | — | 6 / 7 | differs | *"smaller than it sounds"* |
| p034 | — | §03 | The cost model | **137 ms per account** on real PostgreSQL, gather and check are 88% · 1,284 ≈ 3 min · 10,000 ≈ 23 min · 25,000 ≈ 57 min · **40,000 (top of the ICP) ≈ 91 min** · request wall ≈ 60 s | count | — | — | measured | *"And the API still tells every caller that no such measurement exists. No defect row exists for it."* |
| p035 | — | §03 | Three non-negotiables | the clerk never waits (17.0) · resume without re-walking — *"a worker killed at 9,000 of 10,000 pays 22 minutes again"* (17.0) · re-pricing one decision re-checks one account (17, 17.10) | instruction | — | — | no | |
| p035 | — | §03 | The renamed rail | `Scope · Check · Sign off · Send` (was *What to bill · Review · Sign off · Send*) | label | — | — | no | |

**The twelve engine/screen disagreements, in full (p029–p030):**

| # | The engine | The screen | Cited |
|---|---|---|---|
| 1 | Emits **nine** case kinds, never a late fee or extra charge | Declares **fifteen**, gives two their own tab and a bulk action | `DEF-2596` |
| 2 | Computes **no money** in phase 1 | Asks a decision per account on step 3 | **THE ROOT OF THIS REDRAW** |
| 3 | `mark_for_later` / `retry_account` complete and routed | Step 4 draws all three draft powers switched off — *"none of those three has anywhere to send its request"* | `DEF-2841` · `DEF-2856` |
| 4 | `flagged_drafts` raises `NotImplementedError`, zero callers | Step 4 names three actions on unusually-large bills as inert `<span>`s | `DEF-2855` |
| 5 | Writes `bill_runs.status='draft'` once, nothing advances | A Status column, so every finished run reads **Draft for ever** | `DEF-171` · `DEF-602` |
| 6 | Serves `run_no` null | Shows a Run column | `api.py:2092` |
| 7 | `background: true` → 202 + poll address | Called inline, **two minutes at eight grey bars** | `DEF-1084` |
| 8 | Refuses an account whose meter was simply not read | A sentence blaming a **missing meter multiplier** | `DEF-3221` |
| 9 | Produces **no bill at all** for an account whose customer type has no base charge | Lists it nowhere; the total is **silently short** | `DEF-2381` |
| 10 | Nine cross-module seams once per account | **66,053 SQL statements at 1,000 accounts**, uncached by ruling | `DEF-2704` |
| 11 | **Caps a run at 25,000 accounts** | Offers no way to bill a subset, so a **40,000-account utility cannot run a cycle** | `DEF-BIL-4224` |
| 12 | Serves `customer_name` null on every run-case row (a declared seam limit) | Identifies accounts **by number only** | `selectors.py:3206-3210` |

### 5.1 · Entry **16 Scope** — STEP ONE (p046–p048; ASCII zone sketch p035–p036)

`Blocked S89` · `New build S38 S90 S95` · `New read S46` · `Exists behind S24 S25 S26 S34`
meta: `step 1 of 4 — what to bill · /:tenant/billing/run · S31 · BIL-02 · was step 1 of 6`
Q: *"It is the end of the month. Bill everybody — and let me settle the routine decisions
before I start, not one account at a time afterwards."*
band: **BUILD THIS · New build · "Two inputs become five groups, and pricing starts here" ·
CLOSES `BIL-S24` · `BIL-S25` · `DEF-106` · `DEF-1084`**

| Page | Frame | Entry | Element | Drawn value | Kind | Chip | Stage | In the product? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| p046 | REDESIGN | 16 | Page title | `Run bills` | label | — | — | yes | |
| p046 | REDESIGN | 16 | Header action | `Save & exit` | control | — | — | yes | carry-over: UNCHANGED, steps 1–3 |
| p046 | REDESIGN | 16 | Step line | `Step 1 of 4 · nothing has been created yet` | fact | — | — | no | ⚠ p035's zone sketch says *"nothing has been **written** yet"* — two spellings of one line |
| p046 | REDESIGN | 16 | Journey rail | `1 Scope` (active) `2 Check` `3 Sign off` `4 Send` | control | — | — | no | a completed step is a door — step 1 returns to Scope without losing the priced run |
| p046 | REDESIGN | 16 | Group head A | `THE CYCLE` | label | — | — | no | |
| p046 | REDESIGN | 16 | Billing cycle | dropdown `Monthly · Sep 2026`, helper `Silver Creek · 09-A` | control | — | — | differs | was raw ISO dates |
| p046 | REDESIGN | 16 | Period, last | `LAST 01 Aug – 31 Aug 2026` · `RUN-0002 · 1,263 bills` | fact | — | — | no | |
| p046 | REDESIGN | 16 | Period, this | `THIS 01 Sep – 30 Sep 2026`, date pickers | control | — | — | no | was not on the screen at all |
| p046 | REDESIGN | 16 | Continuity tag | `CONTINUOUS — NO GAP, NO OVERLAP` | fact | — | — | no | three states, §5.1a |
| p047 | REDESIGN | 16 | Bill date | picker `09/30/2026`, helper `Prices at this date` | control | — | — | differs | was a bare text box |
| p047 | REDESIGN | 16 | Due date | picker `10/21/2026`, helper `Bill date + 21 days to pay` | control | — | — | no | was not on the screen at all |
| p047 | REDESIGN | 16 | Group head B | `SCOPE` ① | label | — | — | no | **NEW READ** |
| p047 | REDESIGN | 16 | Which accounts | dropdown `Every account in the cycle`, helper `Or a route, an area, or a named set.` | control | — | — | no | ① the answer to the 25,000 ceiling against a 40,000 ICP — `DEF-BIL-4224` high |
| p047 | REDESIGN | 16 | Also include | checkbox ☑ `The 21 accounts held from RUN-0002`, helper `Waiting 11–27 days.` | control | — | — | no | ② **NEW** — `DEF-2843` |
| p047 | REDESIGN | 16 | Group head C | `WHAT THIS COVERS` | label | — | — | no | read-only; zone B holds no controls at all |
| p047 | REDESIGN | 16 | Units in the cycle | `1,502` | count | — | — | no | |
| p047 | REDESIGN | 16 | Accounts to bill | `1,284` | count | — | — | no | **two numbers, not one** — the gap is where every master failure lives |
| p047 | REDESIGN | 16 | Master accounts | `11` · `229 areas · 1 blocked` | count | Masters | — | no | ⚠ p092's spec text says *"3 of the 11"* — `DEF-BIL-5281` |
| p047 | REDESIGN | 16 | Meters this cycle | `1,598` · `+ 96 sub-meters` | count | — | — | no | |
| p047 | REDESIGN | 16 | Points with no meter | `1,526` · `billed without a reading` | count | Base charge only | — | no | sewer and fire; what step 2's *Base charge only* chip counts |
| p047 | REDESIGN | 16 | Services | `Services · 3 of 11` — `W 1,502 units` `S 1,480 units` `F 46 lines` | fact | — | — | no | **read-only chips, NOT a chooser** — see the red band, §9 |
| p047 | REDESIGN | 16 | Unresolved link | `3 unresolved from the last run  see the held queue →` | absence | — | — | no | count computed from an unpaginated list that sorts in memory — honest at 3 |
| p047 | REDESIGN | 16 | Last time | `Last time: 1,263 bills` | fact | — | — | no | kept, *"but only just"* — no money beside it |
| p047 | REDESIGN | 16 | Group head D | `DEFAULTS` ③ | label | — | — | no | **NEW — *"the single biggest error-reducer in this redraw"*** |
| p047 | REDESIGN | 16 | Default · no reading | dropdown `Estimate from history` | control | Missing read | — | no | every option states whether it **bills** or **holds** |
| p047 | REDESIGN | 16 | Default · unusually large | dropdown `Hold it for review` | control | Unusually large | — | no | |
| p047 | REDESIGN | 16 | Default · unusual days | dropdown `Pro-rate by days`, helper **`Holds the bill - pricing not built`** | consequence | Unusual days | — | no | ⚠ *"Pro-rate"* here, *"Prorate"* on 17.5 |
| p047 | REDESIGN | 16 | Label this run | text `September, after the water rate change` | control | — | — | no | ④ **NEW** — `DEF-171` · `DEF-602`, both high |
| p047 | REDESIGN | 16 | Group head E | `ALREADY RUN FOR THIS CYCLE` | label | — | — | differs | the past-runs table MOVED here, scoped to this cycle |
| p047 | REDESIGN | 16 | Past-runs columns | `RUN · LABEL · STARTED · BY · ACCOUNTS · STATUS · ACTIONS` | column | — | — | differs | the *no actor column* panel was **REMOVED — ruled by fact**: `bill_runs.run_by` exists, is populated and is served |
| p047 | REDESIGN | 16 | Past run, issued | `RUN-0002 · August cycle · 09/02/2026 04:00 · Vijay Bikkad · 1,284 · Issued` + 👁 | fact | — | — | no | |
| p047 | REDESIGN | 16 | Past run, open | `RUN-0003 · September, first attempt · 09/11/2026 07:40 · Dana Reyes · — · Open — not signed off` + `Take it over` | control | — | — | no | ⑤ **NEW** — `DEF-106` high |
| p047 | REDESIGN | 16 | Open-run sentence | `Dana Reyes has this cycle open. Take it over, or ask them to sign off.` | instruction | — | — | no | |
| p047 | REDESIGN | 16 | Commit caveat | `About three minutes, in the background. You can close this tab.` | consequence | — | 1–5 / 1–6 | no | |
| p047 | REDESIGN | 16 | Commit | `Check this run →` ⑥ | control | — | — | differs | `POST /billing/runs/{id}/calculate` with `background: true` → 202 + poll — **the mode has existed and gone uncalled since 11 August** (`DEF-1084`) |
| p047 | REDESIGN | 16 | Footer stamp | `BIL-02` | label | — | — | n/a | |
| p035 | REDESIGN | 16 | Consequence line | `With these defaults, 12 accounts will need you and 15 will be held` | consequence | — | — | no | zone C's footer in the ASCII sketch |
| p035 | REDESIGN | 16 | Commit (sketch) | `Prepare — looks, writes nothing, takes ~2 min →` | control | — | — | no | ⚠ the drawing's button reads `Check this run →`; the sketch's reads `Prepare` |

#### 5.1a · The three period states, with their words (p048)

| State | Sentence | Behaviour |
|---|---|---|
| CONTINUOUS | *"This period starts the day after the last one ended. No gap, no overlap."* | proceeds |
| GAP | *"2 days were never billed: 30–31 Aug."* | warns |
| OVERLAP | *"1 day would be billed twice: 31 Aug."* | **"This one should refuse"** |

### 5.2 · Entry **17.0 Checking** — IN FLIGHT (p049–p050) ⚠ the frame nobody had opened

`New build S96` · `Exists behind S40 S41 S45`
meta: `/:tenant/billing/run · between Scope and Check · stages 1–5, pure · nothing written`
(**code stages 1–6**)
Q: *"I pressed Prepare on 25,000 accounts. Do not show me a spinner for an hour — let me
start on what you have already found."*

| Page | Frame | Entry | Element | Drawn value | Kind | Chip | Stage | In the product? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| p049 | REDESIGN | 17.0 | Header action | `Leave it running` | control | — | — | no | **not** `Save & exit` — the only frame in §03 with a different header button |
| p049 | REDESIGN | 17.0 | Step line | `Step 2 of 4 · 09-A · September, after the water rate change · checking since 07:55` | fact | — | — | no | |
| p049 | REDESIGN | 17.0 | KPI 1 | `CHECKED SO FAR` **9,412** / `of 25,000` | count | — | 1–5 / 1–6 | no | |
| p049 | REDESIGN | 17.0 | KPI 2 | `WOULD BILL` **$2,361,904** / `so far` | count | — | — | no | |
| p049 | REDESIGN | 17.0 | KPI 3 | `NEEDS YOU` **87** (red) / `$31,204 at stake` | count | — | — | no | |
| p049 | REDESIGN | 17.0 | KPI 4 | `HELD SO FAR` **141** / `by your defaults` | count | — | — | no | |
| p049 | REDESIGN | 17.0 | KPI 5 | `BLOCKED SO FAR` **38** (red) / `a fix elsewhere` | count | — | — | no | **FIVE tiles in flight; the settled frame has four** |
| p049 | REDESIGN | 17.0 | Progress band | `Checking` + bar + **`about 35 minutes left`** | fact | — | — | no | *"What is left on the header is the one fact that appears nowhere else: how long."* |
| p049 | REDESIGN | 17.0 | The sentence | **`Nothing is being billed yet. You can close this page — it keeps going.`** | consequence | — | — | no | *"Six words carry the whole screen"* · *"It was four sentences and it is now two"* |
| p049 | REDESIGN | 17.0 | Band strip | the same 26 tags, Frame B counts (§3) | count | all 26 | — | no | *"the same twenty-six on every screen"* |
| p049 | REDESIGN | 17.0 | Toolbar | `Search account #, customer or address…` · `Service ▾` · `Route ▾` · `+ Filter ▾` · export · column selector | control | — | — | no | |
| p049 | REDESIGN | 17.0 | Bulk bar | `2 selected` · `Estimate from history` · `Hold these` · **`Decide on what has arrived — the rest keeps checking.`** | control | — | — | no | **no late-fee waiver in flight** |
| p050 | REDESIGN | 17.0 | Table columns | `☐ · ACCOUNT · SERVICES · USAGE · WOULD BILL · WHAT IS WRONG · WHAT TO DO` | column | — | — | no | ⚠ **`WOULD BILL`**, where the settled frame says `AMOUNT` |
| p050 | REDESIGN | 17.0 | Footer | `Showing 1–3 of 31 so far` | count | Missing read | — | no | *so far* — the list grows under the clerk |
| p050 | REDESIGN | 17.0 | Frame stamp | `1440 × desktop · the check, in flight` | label | — | — | n/a | |
| p050 | REDESIGN | 17.0 | ⚠ the verdict | **`This screen does not exist. At 25,000 accounts it is the difference between a usable product and an unusable one.`** | absence | — | — | **no** | the single strongest statement in §03 |

### 5.3 · Entries **17.L1 – 17.L5** — the five layers of screen 17 (p036–p045)

Each layer is drawn once at full strength with the other four dimmed. `A LAYER OF SCREEN 17`.
All five carry `/:tenant/billing/run · screen 17, one layer at a time · the other four are
dimmed, not absent`.

| Page | Frame | Entry | Element | Drawn value | Kind | Chip | Stage | In the product? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| p036 | REDESIGN | 17.L1 | Layer name | `Step rail · LAYER ONE · 4 steps` | label | — | — | no | Q: *"Where am I, how much is left, and can I go back?"* |
| p036 | REDESIGN | 17.L1 | The rail | `1 Scope · 2 Check (active) · 3 Sign off · 4 Send` | control | — | — | no | **Four, not six** — a clerk counting steps is estimating how long this will take |
| p037 | REDESIGN | 17.L1 | Sub-head | `Step 2 of 4 · 09-A · September, after the water rate change · priced 09/11/2026 07:55` | fact | — | — | no | |
| p037 | REDESIGN | 17.L1 | Rule | *"What it must never do: carry a count, a total or a warning."* | instruction | — | — | no | layer 2 exists for the second reading |
| p038 | REDESIGN | 17.L2 | Layer name | `Run state · LAYER TWO · 4 cells · GET /billing/runs/{id}` | label | — | — | no | Q: *"What is the state of this run, right now, whatever I happen to be looking at?"* |
| p038 | REDESIGN | 17.L2 | KPI 1 | `READY TO BILL` **1,251** / `$342,180.00` | count | Ready | — | no | |
| p038 | REDESIGN | 17.L2 | KPI 2 | `NEEDS YOU` **12** (red) / `$4,206.55 at stake` | count | — | — | no | *"A count says how much work; the money says whether the work matters."* |
| p038 | REDESIGN | 17.L2 | KPI 3 | `HELD` **21** / `15 by a default · 6 blocked` | count | — | — | no | Held carries its split |
| p038 | REDESIGN | 17.L2 | KPI 4 | `RUN TOTAL` **$346,386.55** / `updates as you decide` | count | — | — | no | reads `updating` while a re-price is in flight |
| p039 | REDESIGN | 17.L2 | **The rule** | **`A filter changes the list and never these four cells.`** | instruction | — | — | no | ⚠ broken by 17.21 — `DEF-BIL-5276` |
| p039 | REDESIGN | 17.L3 | Layer name | `Navigation · LAYER THREE · ` **`4 bands · 15 chips · generated, never declared`** | label | — | — | no | ⚠ **contradicts its own annotation and drawing** — `DEF-BIL-5272` |
| p040 | REDESIGN | 17.L3 | The band strip | **seven bands, twenty-six tags** (§3) | count | all 26 | — | no | *"bounded above and below by a rule, each band separated by a hairline, band names in a fixed label so the tags line up in a column"* |
| p040 | REDESIGN | 17.L3 | Band order | `Needs you → answered by your default → held → everything else` | instruction | — | — | no | **ordered by obligation — a clerk is finished when the first band is empty** |
| p040 | REDESIGN | 17.L3 | Held is three questions | why it is here · where the fix is · the reason · how long it has waited | fact | Held | — | no | *"All four partition the same rows, and the arithmetic is checked."* |
| p040 | REDESIGN | 17.L3 | Age is on step 2 | because step 1 sweeps up — *"also include the 21 accounts held from RUN-0002"* | fact | Over 60 days | — | no | *"An account held month after month is the thing that quietly loses revenue"* |
| p041 | REDESIGN | 17.L3 | Chips are generated | *"A case kind the engine did not raise gets no chip."* | instruction | — | — | differs | the as-built screen declares fifteen where nine are emitted → **three tabs whose only content is an explanation that the feature is not built** |
| p041 | REDESIGN | 17.L3 | The set never changes | *"the same on all thirty frames"* — three screens used to disagree: in-flight check **8** tags, arrears view **10**, chip-wide bulk action **3** | fact | — | — | no | ⚠ p043 says **twenty-nine** frames; 29 is the count that reconciles |
| p041 | REDESIGN | 17.L3 | **Tags count cases** | *"A tag counts CASES; a band counts ACCOUNTS. Twelve accounts raise nineteen case rows"* | instruction | Needs you | — | no | ⚠ every drawn strip sums to the band — `DEF-BIL-5273` |
| p041 | REDESIGN | 17.L3 | Filters moved out | search, `Service`, `Route`, `+ Filter` are **below** the bands, in layer 4 | control | — | — | no | *"Layer 3 is now nothing but tags."* |
| p041 | REDESIGN | 17.L4 | Layer name | `Selection · LAYER FOUR · appears only with a selection` | label | — | — | no | Q: *"I have picked some rows. What can I do to all of them at once, and what will it cost?"* |
| p042 | REDESIGN | 17.L4 | The gap it closes | **`There were no checkboxes on any row, on any frame.`** | absence | — | — | **no** | |
| p042 | REDESIGN | 17.L4 | Selector column | 38px, first, pinned | control | — | — | no | |
| p042 | REDESIGN | 17.L4 | Header checkbox | tri-state — empty, some, all — **selects THIS PAGE** | control | — | — | no | *select all in the chip* is a separate, explicit control |
| p042 | REDESIGN | 17.L4 | Selection rules | changing chip **clears** the selection and says so · paging **keeps** it with a running count · shift-click selects a range · a row decided by hand is **never overwritten** and is counted separately · a selection spanning bands becomes one call per case kind, and the bar says `3 actions` | instruction | — | — | no | |
| p042 | REDESIGN | 17.L4 | No selector where nothing can be actioned | *"twenty-eight frames of twenty-nine"* — 17.11 has none | control | — | — | no | ⚠ 17.14 Ready draws one and should not — `DEF-BIL-5282` |
| p042 | REDESIGN | 17.L4 | PO ruling, verbatim | *"if clark say 231 then all 231 should be actioned"* | fact | — | — | no | a selection is a **snapshot** pinned when the clerk makes it |
| p042 | REDESIGN | 17.L4 | Result sentence | `231 actioned. 2 have since been read and will bill on the reading, not the estimate.` | fact | — | — | no | |
| p043 | REDESIGN | 17.L4 | Size floor | ids held client-side are fine at **231** and at **5,908**; above **10,000 in one chip** select-all refuses and asks the clerk to narrow it | consequence | — | — | no | |
| p043 | REDESIGN | 17.L4 | ⚠ standing refusal | *Estimate from history* **refuses today** — the server accepts a quantity and a unit and **no screen has ever sent them**. *"Reported in the endpoint's own docstring; no defect row."* | absence | Estimated | — | **differs** | 17.16 and 17.22 are both built on it |
| p043 | REDESIGN | 17.L4 | PO ruling, verbatim | *"you can calculate it on screen - in such case we will have to show work in progress to clark"* | fact | — | — | no | 2026-09-12 — the on-screen-calculation ruling |
| p043 | REDESIGN | 17.L4 | Column contract | Account **24ch** · Services **94px** (four badges and their gaps) · a quantity **10–12ch** · a date **14–16ch** · money **13ch** · What to do **240px** · What is wrong **the remainder** | column | — | — | no | *"Verified across 595 cells in 29 tables: nothing overflows its column at any width from 1920 down to 400."* |
| p043 | REDESIGN | 17.L4 | Toolbar is fixed | same on all **twenty-nine** frames: search, Service, Route, + Filter, export, column selector | control | — | — | no | ⚠ 17.21 adds two — `DEF-BIL-5276` |
| p043 | REDESIGN | 17.L4 | Bulk confirms its arithmetic | estimating four shows **+$124.70**; holding three shows **−$3,737.00** | consequence | — | — | no | screens 17.16–17.20 |
| p043 | REDESIGN | 17.L4 | Scale sentence | this run has **12** rows needing a decision; a 25,000-account cycle has roughly **234** | count | — | — | no | |
| p044 | REDESIGN | 17.L5 | Layer name | `One row · LAYER FIVE · 6 columns · the order never moves` | label | — | — | no | Q: *"One account. What is it, what is wrong with it, what will it be billed, and what am I going to do about it?"* |
| p045 | REDESIGN | 17.L5 | Column grammar | **who → what → the facts → how much → what is wrong → what to do** | column | — | — | no | *"The first two and last two are in the same place on all fifteen chips"* |
| p045 | REDESIGN | 17.L5 | What is wrong | **a SENTENCE**, not a code | fact | — | — | differs | |
| p045 | REDESIGN | 17.L5 | Money is never blank and never a false zero | `not priced` where nothing could be computed · **`$0.00` in red** where the engine really did produce zero and that is the defect | fact | — | — | no | |
| p045 | REDESIGN | 17.L5 | One row, one decision | a row with a fix elsewhere carries the door — `Enter the reading →`, `Fix the plan →`, `See the 12 units →` | control | — | — | no | |
| p045 | REDESIGN | 17.L5 | A master says so on the row | `covers 12 units`, priced per connection, `$70.17` on two plans | fact | Masters | — | no | |
| p045 | REDESIGN | 17.L5 | Shared rules | layer 2 is the run, layer 3 is the view · four groups, not twenty-six chips in a row · **one spacing scale: 12px inside a band, 16px between the region and its neighbours** · the bulk bar exists only with a selection · a decision re-prices in the background (`updating`) · **nothing lives behind a hover** — a refusal is five or six words and colour is never the only signal | instruction | — | — | no | B14 rule 33 |

**The settled table rows drawn on the layer frames** (p037; illustrations, rule 2):

| Account | Services | Usage | Amount | What is wrong | What to do |
|---|---|---|---|---|---|
| 100251 Northside Warehouse · 22 Mill Rd | W S F | 31 kgal | $1,284.40 | *"Used 4.2× its usual 7.4 kgal. Meter M-9112, read 09/01."* | `Hold for review` |
| 100263 M. Okonkwo · 14 Birch Ln | W S | — | **not priced** | *"No reading was taken. Last read 07/28."* | `Estimate` + `Enter the reading →` |
| 100288 Cedar Ridge HOA · 105 Cedar Ridge Way | T | 1 cart | **$0.00** | *"No base charge covers this customer type. Commercial · Trash."* | `—` + `Fix the plan →` |
| 100302 Hillcrest Apartments · covers 12 units | E W | 112 kgal | $70.17 | *"Two connections, two plans. Priced per connection."* | `Bill as is` + `See the 12 units →` |
| footer | | | | `Showing 1–4 of 12 that need you` · `Rows per page 50` | |

### 5.4 · Entry **17 Check** — STEP TWO, settled (p051–p053)

`New build S27 S83 S90 S91 S92 S96` · `New read S73` · `Exists behind S26 S28 S32 S40`
meta: `step 2 of 4 · /:tenant/billing/run · replaces steps 2, 3 and 4 of six · BIL-02`
band: **BUILD THIS · New build · "One screen, priced, filterable, decisions inline" ·
CLOSES `BIL-S26` · `BIL-S27` · `BIL-S28`**

| Page | Frame | Entry | Element | Drawn value | Kind | Chip | Stage | In the product? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| p051 | REDESIGN | 17 | KPI strip | the four cells of 17.L2, Frame A | count | — | — | no | |
| p051 | REDESIGN | 17 | Band strip | 26 tags, Frame A | count | all 26 | — | no | |
| p051 | REDESIGN | 17 | Toolbar + bulk bar | as 17.L4 | control | — | — | no | |
| p051 | REDESIGN | 17 | Table | the four rows above | column | — | — | no | ⚠ row 1 reads **`Used 4× its usual`** here and **`4.2×`** on every layer frame; the arithmetic (31 ÷ 7.4) supports 4.2× |
| p052 | REDESIGN | 17 | Row 4, alternate | `100302 D. Whitfield · 8 Kiln St · W · 12 kgal · re-pricing… · "Reading corrected 2 minutes ago" · waiting for the new amount` | fact | — | — | no | the same account number as Hillcrest Apartments — an illustration clash, rule 2 |
| p052 | REDESIGN | 17 | Reconciliation | `All 1,284 accounts in the cycle are accounted for: 1,251 ready, 12 need you, 21 held by your defaults, 0 broke. 1,251 + 12 + 21 = 1,284.` | fact | — | — | no | ⚠ *"21 held by your defaults, 0 broke"* contradicts the KPI's *"15 by a default · 6 blocked"* — `DEF-BIL-5280` |
| p052 | REDESIGN | 17 | Commit | `Sign off on this run →` with `12 accounts still need a decision.` | control | — | — | no | |
| p053 | REDESIGN | 17 | Band table | *"the three bands"* heading over **four** rows: Needs you **seven** · your default **two** · Held **four** · Everything else **two** | count | — | — | no | ⚠ heading says three and lists four; Held and Everything else both disagree with the drawn strip — `DEF-BIL-5272`, and `DEF-BIL-5257` already holds the Held half |
| p053 | REDESIGN | 17 | Scope of what follows | *"The twenty screens that follow are step 2 with one chip selected, and one per bulk action."* | fact | — | — | no | |

### 5.5 · Entries **17.1 – 17.15** — one frame per chip

Every frame carries the same shell (KPI strip, 26-tag band strip, toolbar, bulk bar, table,
`Rows per page 50`, frame stamp `1440 × desktop · step 2 · one chip`) and differs only in the
chip selected, the table's middle columns, the bulk bar and the choices. Only the
differences are inventoried.

| Page | Entry | Badge | Flags | meta | Table columns (middle) | Rows drawn / footer | Bulk bar | The choices | Notes |
|---|---|---|---|---|---|---|---|---|---|
| p056–57 | **17.1 No read** | `THREE WAYS` | `New build S91 S92` · `Exists behind S32 S33 S47 S49` | `4 rows · missing_read` | `LAST READ` | **3 drawn / `Showing 4 of 4`** ⚠ | `3 selected · Estimate from history · Hold these · Bill without the service` + *"All three apply to every row here. A mixed selection offers only what they share."* | estimate it · hold the account · bill without the service | `DEF-BIL-5279`. Rows: 100263 (44 days ago), 100341 *"dog on premises"*, 100398 *"Meter never read. M-9210 was fitted 08/22"*; all three `not priced` |
| p058 | **17.2 Unusually large** | `COMPARISON` | `Exists behind S32 S33 S47` | `3 rows · high_usage` | `THIS PERIOD · USUAL` | 3 / `Showing 3 of 3` | `2 selected · Bill as is · Investigate — holds` + *"Both apply in bulk. Only the late-fee waiver is one at a time."* | Bill as is · Investigate | *"Your threshold is 200%"* is printed on the row |
| p059 | **17.3 Unusually small** | `QUIET HALF` | `Exists behind S32 S33 S47` | `1 row · low_usage` | `THIS PERIOD · USUAL` | 1 / `Showing 1 of 1` | `1 selected · Bill as is · Investigate — holds` | Bill as is · Investigate | *"Same shape, opposite tail"*; *"Your floor is 25%"* |
| p060–61 | **17.4 Zero use** | `BASE BILLS` | `Exists behind S32 S33 S47` | `1 row · no_usage` | `USAGE 0 kgal` | 1 / `Showing 1 of 1` | — | **Include — bill the base** · Exclude (**holds**) | *"Read is zero, not missing."* A zero read is not a missing one |
| p061–62 | **17.5 Unusual days** | `UNPRICED` | `Exists behind S32 S33 S47` | `1 row · days_threshold` | `PERIOD COVERED · DAYS` | 1 / `Showing 1 of 1` | `1 selected · Bill as is · ` **`Prorate to the cycle's days`** *(disabled)* · `Wait for the next cycle — holds` + *"Prorate is offered per row, not in bulk"* | **Prorate to the cycle's days — `holds the bill, pricing not built`** · Wait for the next cycle · Bill as is | *"the single most important label on any of these screens"* — two of the three choices produce **no bill at all** |
| p063–64 | **17.6 Meter changed** | `TWO SPANS` | `Exists behind S32 S33 S47` | `1 row · replacement` | `THE TWO SPANS · USAGE 4.1 + 5.8 = 9.9 kgal` | 1 / `Showing 1 of 1` | `1 selected · Bill as is · Prorate both segments` *(disabled)* `· Investigate — holds` | Bill as is · Prorate both segments *(unpriced)* · Investigate | both meter numbers on the row; `See both meters →` |
| p064–65 | **17.7 Multiplier** | `TENFOLD` | `Exists behind S32 S33 S47` | `1 row · meter_factor` | `RAW → BILLED 820 → 8,200 · FACTOR 1 → 10` | 1 / `Showing 1 of 1` | `Confirm the factor · Investigate — holds` | Confirm the factor · Investigate | *"Why this is not a usage case: the reading is fine. What changed is the number the reading is multiplied by."* |
| p065–66 | **17.8 Estimated** | *(by default)* | — | `44 rows · estimated_read` | `ESTIMATED · BASIS` | 2 / **`Showing 50 of 44`** ⚠ | `44 selected` + *"Your step-1 default already chose Keep the estimate for all 44."* | Keep the estimate | `DEF-BIL-5279`. BASIS is a sentence: *"Average of the last 3 reads · 7.9, 8.4, 8.3"* |
| p066–67 | **17.9 Base only** | `TWO CAUSES` | — | `31 rows · base_only_billing` | `USAGE` | 2 / `Showing 31 of 31` | `31 selected · Include · Exclude — holds` + *"Your step-1 default already chose Include for all 31."* | Include · Exclude | *"Two different reasons, one chip"* — not metered at all, or a vacation hold |
| p068 | **17.10 Held now** | `YOUR DEFAULTS` | `Exists behind S32 S47` | `15 rows · one exclusion row each` | `THE CASE · HELD BY · WOULD BILL` | 3 / `Showing 15 of 15` | `3 selected · Change the decision · Bill these as they stand` + *"Changing a decision re-prices in the background; the run total updates when it lands."* | Change to Estimate / Change to Bill as is | **`HELD BY` names the default and the step it was set on** — *"tell me which default did it, and let me change my mind here"* |
| p069–70 | **17.11 Account fix** | `UPSTREAM` | `New build S39` · `Exists behind S32 S34 S47` | `3 rows · stage resolve-subscription` (**code 1**) | `COVERS · AT RISK · WHY IT CANNOT BE BILLED · WHAT CLEARS IT` | 3 / `Showing 3 of 3` | **`Retry now` DISABLED** + *"Retry is not offered here: none of these is cleared by pressing it. Two wait on a ruling, one on an edit elsewhere."* | **NO CHOICE COLUMN AT ALL** | ⚠ the refusal sentence describes the **pre-ruling** five-row state; the annotation says the rulings landed and three real fixes remain. ⚠ row 3 draws `AT RISK $0.00` against *"Never $0.00 — a zero here would be a claim"* — `DEF-BIL-5275` |
| p070–71 | **17.12 Read fix** | `PART RETRY` | `Exists behind S32 S47` | `2 rows · stage measure-consumption` (**code 2**) | same | 2 / `Showing 2 of 2` | **`Retry now` ENABLED** + *"Retry is offered on the cart row: once the count is entered it succeeds. It is not offered on the dispute."* | none | *"Permission is stated, not implied"* — `A System Admin clears a dispute` |
| p072 | **17.13 Rates fix** | `MANY ACCOUNTS` | `Exists behind S32 S47` | `1 row · stage price-usage` (**code 3**) 🔒 | same | 1 / `Showing 1 of 1` | `Retry now` ENABLED + *"After dating a version, retry re-prices this account without re-running the whole run."* | none | **the sentence that matters: *"It affects every account on that schedule."*** |
| p073–74 | **17.14 Ready** | `SKIM ONLY` | `Exists behind S32 S34 S47` | `1,251 rows · nothing raised` | **four columns only: `ACCOUNT · SERVICES · USAGE · AMOUNT`** | 4 / `Showing 50 of 1,251` | **`No bulk actions. There is nothing here to decide — that is what makes a row ready.`** | none | ⚠ draws selection checkboxes against its own *"no selection boxes"* — `DEF-BIL-5282`. Sorts by Amount **on the server**; **fifty a page, no cap, no whole-run load** |
| p074–75 | **17.15 Masters** | `CROSS-CUTTING` | `New build S39` · `Exists behind S32 S34 S47` | `11 rows · cuts across every band` | `COVERS · SERVICES · PLANS · AMOUNT · STATUS` | 4 / `Showing 11 of 11` | **`Apply a default to these` REFUSED** + *"A master takes no bulk default. Three of the four refusals are data or rule problems upstream, and a default cannot answer either."* | none in bulk | **`COVERS` is the first real column — before services, before money.** Rows show the per-connection arithmetic on the face: `$69.60 + $0.57 fee` and `2 × $12.00 base + 2 × $20.00` |

### 5.6 · Entries **17.16 – 17.20** — the five bulk confirms

Every one is a dialog. The stated footer rule (p077) is **Cancel a ghost on the left, the
commit on the right naming the act and the count — never `OK`**; the commit shows
`Working…` and cannot be pressed twice, and Cancel is unavailable once the write is in
flight. ⚠ **Six dialogs in §03 draw the inverse — `DEF-BIL-5278`.**

| Page | Entry | Badge | Flags | Title | Body | The arithmetic | Footer | Notes |
|---|---|---|---|---|---|---|---|---|
| p076–77 | **17.16 Estimate all** | `BEFORE AFTER` | `New build S42` · `Exists behind S47 S48 S49` | `Estimate 4 accounts from history` | *"Four accounts will be estimated and billed in this run. Each estimate is computed from that account's own history, not from an average of the four."* + per-row `ESTIMATE · BASIS · WOULD BILL`, one row **`cannot estimate`** · `3 of 4 will change. The fourth has no history to estimate from, so it stays on Needs you.` | `RUN TOTAL NOW $346,386.55 · THIS ACTION ADDS + $124.70 · AFTER THIS ACTION $346,511.25` ✅ | `Cancel` · `Estimate these 3` | **the button counts 3, not 4** — *"A bulk action that silently skips part of its selection is how a clerk comes to believe an account was handled."* ⚠ emphasis drawn inverted |
| p077–78 | **17.17 Hold these** | `TAKES REASON` | `New build S42` · `Exists behind S47 S48` | `Hold 3 accounts out of this run` | *"Three accounts will not be billed in this run. They go to **Held accounts** and are billed later by a catch-up run."* + `Why are these being held?` dropdown (`Reading looks wrong`, *"Chosen from your own reason list. Required."*) + `Note (optional)` (*"Goes on the account's record and on the queue row."*) | `RUN TOTAL NOW $346,386.55 · THIS ACTION REMOVES − $3,737.00 · AFTER $342,649.55` ✅ | `Cancel` · **`Hold these 3` (DANGER TIER, red)** | **the only bulk action on step 2 that removes revenue** — B14's danger tier, *"even though it is reversible"*. Writes one row per account: account, reason, note, **who** and **when** |
| p078–79 | **17.18 Accept** | `NO CHANGE` | `New build S42` · `Exists behind S47 S48` | `Bill 2 accounts as they stand` | *"Two accounts will be billed at the figures shown, with the unusual usage accepted as correct."* + **the immutability sentence**: *"Accepting a reading does not change it. If the reading is later found wrong, the bill is corrected by a new bill — an issued bill is never edited."* | `RUN TOTAL NOW $346,386.55 · ALREADY IN THE TOTAL: no change · AFTER $346,386.55` | `Cancel` · `Bill these 2 as they stand` | **the honest total is a delta of zero** — *"a clerk should not be looking for money that was never going to move."* *"Primary, not danger."* ⚠ emphasis drawn inverted |
| p080 | **17.19 Confirm factor** | `WHO WHEN` | `New build S42` · `Exists behind S47 S48` | `Confirm the multiplier on 1 account` | *"One account will be billed on the new multiplier. The reading is not in question; the number it is multiplied by is."* + `RAW 820 · FACTOR 1 → 10 · BILLED QUANTITY 8,200 · WILL BILL $1,914.00` + **who and when**: *"The factor was changed on meter M-9007 on 08/20/2026 by T. Alvarez. Last month this account billed $191.40 on a factor of 1. Confirming bills 10× that."* | no change to the run total | `Cancel` · `Confirm the factor` | *"The arithmetic is shown, not implied."* ⚠ emphasis drawn inverted |
| p081–82 | **17.20 Waiver** | `REFUSED` | `New build S42 S77 S102` · `Exists behind S47 S48` | `Waive the late fee` | **`A waiver is one account at a time, with a reason.`** *"You have 3 accounts selected. A late-fee waiver cannot be applied to a selection — the reason is the whole of the evidence it leaves, and one reason covering three accounts is evidence for none of them."* / *"Every other action on this screen works in bulk. This one does not, and that is a rule rather than a limitation of the screen."* | — | `Close` · `Waive on one account…` | **a refusal drawn on purpose** — *"A greyed button with no stated reason looks like unfinished work, and the next lane to pass through will wire it up in good faith and break a signed rule."* Rule id `BR-BIL-060`. ⚠ **`The engine does not currently raise a late-fee case at all` — declared and never emitted, so this screen may be reachable only after that is fixed** |

### 5.7 · Entry **18 Sign off** — STEP THREE (p082–p084)

`New build S43 S50` · `Exists behind S29 S40`
meta: `step 3 of 4 · /:tenant/billing/run · GET /billing/runs/{id}/summary`
Q: *"Before I put my name on this: how many accounts, split how, how much water, how much
money, how much did they already pay, and what am I NOT billing?"*
**Five groups, and the order is the argument: what is billed → what was used → what it is
worth → where the money stands → what is NOT billed.**

| Page | Entry | Element | Drawn value | Kind | Notes |
|---|---|---|---|---|---|
| p082 | 18 | Header action | `Back to Check` | control | |
| p082 | 18 | Step line | `Step 3 of 4 · 09-A · September, after the water rate change · nothing written yet` | fact | |
| p082 | 18 | Group 1 | `WHAT IS BEING BILLED` — In scope **1,284** (`1,502 units in the cycle`) · Regular **1,273** (`one unit each`) · Master **11** (`229 common areas · priced per connection`) · **Bills to create 1,260** (`1,251 clean + 9 you released`) · Not billed **24** (`group E — 1,260 + 24 = 1,284`) | count | column header is `POPULATION`, once, on the rule above the table |
| p083 | 18 | Group 2 | `WHAT WAS USED` — `SERVICE · QUANTITY · UNIT`: W Water **18,402 kgal** · S Sewer **17,118 kgal** · E Electric **122,840 kWh** · T Trash **1,204 carts** · F Fire **46 lines** | count | consumption always with its unit — hard rule 3 |
| p083 | 18 | Group 3 | `WHAT IT IS WORTH` — Charges **$345,672.15** · Credit notes (`23, named →`) **− $4,182.00** · **Net this run $341,490.15** | count | |
| p083 | 18 | Group 4 | `WHERE THE MONEY STANDS` — Owed before this run **$128,402.55** · Payments applied since the last run **− $96,318.20** · Carried into this bill **$32,084.35** · This run's charges **+ $341,490.15** · **Owed after this run $373,574.50** | count | *"foots by construction … the same three lines print on every bill — so the screen and the paper cannot disagree"* |
| p083 | 18 | Group 5 | `WHAT IS NOT BEING BILLED` — Held by a default **18** (`which default →`) · **Blocked 6** (`3 the account or the plan · 2 the read · 1 the rates`) · Nothing to charge for **0** (`correct, and counted`) · **Total unbilled 24** (`~$6,240 not invoiced — an estimate`) · In arrears **312** (`$84,204.60 owed before this bill`) · **On the final rung 1** (`100418 · notice sent 09/09`) | count | **last because it is the one a clerk would otherwise never see, and the only one that costs money when it is wrong**; the two arrears rows are **inside the same table**, not a separate KPI strip |
| p083 | 18 | Group 6 | `SEE ONE BEFORE YOU SIGN` **new** — `Which account` dropdown `100302 · Hillcrest Apartments — master, 2 plans` + `See the specimen →`, helper `Any of the 1,260. This one shows the most.` | control | **BIL-S50** |
| p083 | 18 | Specimen caveat | `Rendered from this run's own figures.` **`No bill number and no due date`** `— both are set when the bill is created.` | absence | *"A specimen is a bill minus exactly two facts"* — it **labels both absences** rather than printing a blank or a guess |
| p083 | 18 | The tick | ☐ `I have looked at the 24 not being billed and the 1 on the final rung.` | control | **names the 24 and the 1** — not a general *are you sure* |
| p083 | 18 | Gate caveat | `Nothing has been written yet.` | consequence | |
| p083 | 18 | Commit | `Sign off and create 1,260 bills` | control | **this is where stage 6 / code stage 7 runs and bills come into existence** |
| p084 | 18 | Why a specimen | *"On 7 September the water rate changed. This run prices 1,284 accounts and this screen says $341,490.15. That figure is equally consistent whether water is $4.10 or $41.00 a kgal … On one bill they read `Water 6.2 kgal at $4.10 = $25.42` and know in a second."* | fact | **a clerk cannot tell a right total from a wrong one by looking at a total** |
| p084 | 18 | Why here, not step 4 | *"At step 4 a wrong rate costs 1,260 corrections. Here the cost of being wrong is zero."* | fact | |
| p084 | 18 | What it costs | the bill's entire content is **one pure function** over stages 1–5's output; stage 6 does two separate things with it — **creates the invoice row** and **mints the bill number**. A specimen is that pure function plus the renderer and **neither of stage 6's two writes** | fact | *"the specimen cannot disagree with the bill, because it is the bill's own payload"* |
| p084 | 18 | It mints no number | *"three re-runs of a 500-account run spend 1,500 numbers on 500 bills"* — stage 6's own comment | consequence | |
| p084 | 18 | 18.1 is gone | this screen and `18.1 The numbers` were the same screen twice — **there is one screen 18** | absence | |

### 5.8 · Entry **19 Send** — STEP FOUR (p085–p086)

`New build S50` · `Exists behind S30`
meta: `step 4 of 4 · /:tenant/billing/run · the bills exist; nothing has been dispatched`
Q: *"You are asking me to send 1,260 bills and I have not looked at a single one. Show me a
real bill first — then tell me exactly what leaves, by what route, and what happens to the
people on AutoPay."*
**Grouping: look at one → how it travels → who pays automatically → send.**

| Page | Entry | Element | Drawn value | Kind | Notes |
|---|---|---|---|---|---|
| p085 | 19 | Header action | `Print set` | control | |
| p085 | 19 | Step line | `Step 4 of 4 · 09-A · 1,260 bills created · nothing has left the building yet` | fact | *"1,260 bills created and 1,260 bills sent are different facts and step 3 already did the first one"* |
| p085 | 19 | Group 1 | `LOOK AT ONE BEFORE IT GOES` — `OPEN · ACCOUNT · AMOUNT · WHY THIS ONE`, three rows: **the biggest surprise** (100302, $70.17, *"A master, two connections, two plans, priced per connection"*) · **an ordinary one** (100101, $48.20) · **an estimate** (100263, $51.30) | control | **three bills chosen rather than the first three** — *"the first three alphabetically tell a clerk nothing"* |
| p085 | 19 | Group 1 footer | `These are the real issued documents, not a sample.` `Open any of the 1,260 →` | fact | served by `GET /invoices/{id}/document.pdf` |
| p085 | 19 | Group 2 | `HOW THESE REACH PEOPLE` — `CHANNEL · BILLS · STATE`: **Print 1,260 `Goes out`** (*"the floor — every bill, always"*) · Email **0** `Nobody elected` (*"the read that says who chose email is not published, so no account can elect it"*) · Text message **0** `Not offered here` (*"the channel exists in notifications; billing's own seam does not name it"*) · In-app **0** `Not offered here` (*"and it needs no vendor, so it is the cheapest of the four to turn on"*) · Customer portal **0** `Not offered here` | absence | **five channels; one works.** *"Every bill goes out on paper, whatever the customer asked for."* |
| p086 | 19 | Group 3 | `AUTOPAY` — On AutoPay **412 · $112,840.55** `Handed to Payments` (*"billing issues; it does not take money"*) · Cash only — no AutoPay **31 · $8,204.10** (*"a standing privilege on the account; never charged"*) · Not on AutoPay **817 · $220,445.50** (*"they pay as they choose"*) · **`412 + 31 + 817 = 1,260.`** | count | the three values sum to **$341,490.15** — Sign off's net ✅ |
| p086 | 19 | The tick | ☑ `I have opened at least one bill from this run.` | control | ⚠ *"You were right: a clerk should not send what they have not seen"* |
| p086 | 19 | Pre-commit sentence | `1,260 to print · 0 by any other channel · 412 handed to Payments for collection.` | consequence | **the button carries the three counts in words** |
| p086 | 19 | Commit | `Send 1,260 bills` | control | last on the screen, on purpose — *"the only genuinely alarming number on the screen — 0 by email — was below the button that made it permanent"* |
| p086 | 19 | ⚠ the better answer | *"A specimen at sign-off, rendered from the priced data before anything is created, would be better still … It is `BIL-S50`, and it is the one thing on this screen I would build next."* | instruction | |

### 5.9 · Entries **17.21, 17.22**

| Page | Entry | Badge | Flags | meta | Element | Drawn value | Notes |
|---|---|---|---|---|---|---|---|
| p088–89 | **17.21 In arrears** | `NEW CHIP` | `New build S44` · `Exists behind S47` | `/:tenant/billing/run · a new chip in Everything else · 312 rows · measured against 09/11/2026` | **KPI strip** | **FIVE cells** — `READY TO BILL 1,251 · NEEDS YOU 12 · HELD 21 · IN ARREARS 312 / $84,204.60 owed · RUN TOTAL $346,386.55` | ⚠ `DEF-BIL-5276` — 17.L2's rule is four cells that a filter never changes |
| p089 | 17.21 | | | | Toolbar | adds **`As at 09/11/2026`** (date picker) and **`Ladder rung ▾`** | ⚠ same defect — p043 says the toolbar is identical on all 29 frames |
| p089 | 17.21 | | | | Bulk bar | `1 selected · Hold these · ` **`Send a notice` DISABLED** ` · Billing does not send notices. The collection ladder does, and it has four rungs of its own.` | *"a second dunning path out of billing means two systems telling one customer different things"* |
| p089 | 17.21 | | | | Columns | `ACCOUNT · SERVICES · OWED NOW · OLDEST UNPAID · WHERE THEY ARE · THIS BILL · WHAT TO DO` | |
| p089 | 17.21 | | | | Ladder states drawn | `Final 48 hours` (`disconnect notice sent 09/09`) · **`RUNG NOT MAPPED`** (`second 5-day — no tier is recorded`) · `First 10-day` · `Friendly reminder` | **one rung cannot be named and the screen says so** — *"choosing one would be a statement to a regulator about what a customer was told"* |
| p089 | 17.21 | | | | Footer | `Showing 1–4 of 312` | |
| p090 | 17.21 | | | | Arrears threshold | seeded at **60 days past due, or twice the account's average bill** — **a proposal, not a ruling** | a tenant setting |
| p090 | 17.21 | | | | `past due` refuses today | *"the tenant's clock does not reach it, and a wrong past-due is a claim about a customer's money"* | **passing the business day makes it computable — one fix, three screens** |
| p090–91 | **17.22 Apply all** | `AT SCALE` | `New build S42` · `Exists behind S47 S48 S49` | `/:tenant/billing/run · a chip-wide bulk action · the 25,000-account case` | Dialog | `Estimate 231 accounts from history` — *"All 231 are actioned. A decision is recorded for every one of them, sharing one action id — you said 231, so 231 it is."* | Set C, §2 |
| p090 | 17.22 | | | | Effect table | Estimated and billed **198** · Actioned, and held **33** (*"No history to estimate from — meters fitted this cycle. **The decision is still recorded**"*) · Already decided by hand **0** (*"never overwritten by a bulk action"*) · Actioned in total **231** | ✅ 198 + 33 + 0 = 231 |
| p090 | 17.22 | | | | Typed-count gate | `Type 231 to confirm` / field `231` / helper *"A bulk action over more than 50 rows asks for the count. It is the one gesture that cannot be made by accident."* | ⚠ the annotation says **198** in both places — `DEF-BIL-5277` |
| p090 | 17.22 | | | | Progress | `Working out 231 estimates…140 done` / *"231 estimates to work out, then 231 rows written. The screen stays usable and the total updates when it lands."* | the 2026-09-12 on-screen-calculation ruling, built |
| p091 | 17.22 | | | | Footer | `Cancel` · `Action all 231` | ⚠ emphasis inverted — `DEF-BIL-5278` |
| p091 | 17.22 | | | | Why mandatory | *"This run has 12 accounts needing a decision. A 25,000-account cycle has **231 in one chip alone**. Ticking rows fifty to a page is not a workflow, it is a reason the cycle is late."* | |
| p091 | 17.22 | | | | Selecting a chip selects the CHIP | *"A select-all that quietly meant **these fifty** is how a clerk comes to believe 231 accounts were handled."* | |

### 5.10 · Units or accounts — the master asymmetry (p091–p094)

**`The cycle scopes units. The bill is per account.` Those are two different numbers, the
gap between them is where every master-account failure lives, and no screen in the product
shows both.**

| | A regular account | A master account |
|---|---|---|
| What the run iterates | metering publishes the **units**; the run resolves them to accounts | the same — *"a master is not a separate population"* |
| Units one bill prices | **one** — the account's own unit | the anchor unit **plus every common area it covers** through an open service agreement |
| If coverage cannot be read | falls back to the one unit, which is correct for it | **refuses, by name** |
| Why the asymmetry is deliberate | — | *"the fallback **is** the defect: a bill for **$41.20 of a $69.60 obligation**, correct-looking on the document and short by an entire common area"* |
| Unoccupied units on the premises | n/a | now priced onto the owner's bill (changed 27 Aug — it used to refuse, footing at $69.60 while $81.60 was owed). **`Open`** — the run still reports them as unbilled anyway |
| Named refusal reasons | none | **three, of which one survives**; *spans two plans* and *repeats a service* were ruled per connection on 2026-09-11 |
| Open defects | — | **three, one red on the branch** |

**The two rulings of 2026-09-11, verbatim and worked:**

| Question | Ruled | Worked |
|---|---|---|
| Two covered areas take the same service — base charge once per bill or once per connection, and do the tier thresholds pool or reset? | **Per connection.** *"per conenction"*. Each connection bills its own base charge and walks its own tier ladder from the bottom. Two electric connections on one bill produce **two base lines and two usage ladders**, not one of each. | Base $12.00, $0.20/kWh, 100 kWh at each of two connections → **$64.00**. The pooled reading would have been **$52.00**. |
| Covered areas sit on different plans — whose taxes, fees, discounts and plan snapshot govern the one bill? | **Per connection.** *"as per connection"*. Each connection is governed by **its own** plan, and the bill carries **one plan snapshot per connection** rather than one for the bill. | Hallway on *Common Electric* (no tax) and irrigation on *Common Water* (2.00% city fee) over **$69.60** → fee **$0.57**, bill **$70.17**. Levied on the whole bill it would have been **$1.39**. |

⚠ **The second ruling REVERSES a recorded ruling and the reversal has to be written down
rather than assumed.** On **2026-08-11** the same question at bill level was answered *"Tax
rates are for bill not for service"*, and the pipeline was built on it: **one plan id
resolves the bill's taxes, its charge codes, its discount rules and its locked-at-issue plan
snapshot** — four places, one id. The document's own reading, and what §03 is drawn to:
**the reversal is NARROW — master accounts covering units on different plans, and nothing
else.** If it was meant generally — every bill's tax levied per service — **that is a
different and much larger change and it moves a signed figure.** `BIL-S39` is the engine
change; the third master refusal, *coverage unresolved*, is untouched by either ruling.

⚠ **The red band on screen 1's services (p092), which has no defect row and no open question
anywhere:** *"The run is keyed on **tenant + cycle + period** and nothing else. A service
scope is accepted, stored and honoured — it just is not in that key. So a clerk who runs
`Water only` for September **consumes the key for September**, and the Sewer run is then
refused as a duplicate. Those accounts are not excluded from anything, so no exclusion row
exists, so they are not in the held queue, so **no catch-up will ever bill them**. … **There
is no defect row and no open question for it — zero rows in the register mention the scope
field.** Until the key carries the scope, **screen 1 shows scope and does not choose it**.
That is `BIL-S38`."*

### 5.11 · Entries **20 – 20.3** — the held queue and its two missing dialogs

| Page | Entry | Badge | Flags | meta | Element | Drawn value | Notes |
|---|---|---|---|---|---|---|---|
| p094–95 | **20 Held queue** | `NO EXIT` | `New build S39 S44` · `Exists behind S35 S36 S100` | `47 rows · /:tenant/billing/pending · exists, and cannot be acted on · BIL-08` | Page title | `Held accounts` | Q: *"Forty-seven accounts have not been billed. Which ones, for how long, what is it worth, and let me bill the ones I have fixed."* |
| p095 | 20 | | | | Header actions | `Export` · `Hold an account` | the second opens 20.2 |
| p095 | 20 | | | | Sub-head | `47 still held · 9 escalated · measured against 09/11/2026` | |
| p095 | 20 | | | | KPI | `STILL HELD 47` (`across 4 cycles`) · `ESCALATED 9` (`older than 14 days`) · `ESTIMATED VALUE ~$11,480` (`not billed — an estimate`) · `OLDEST 71 days` (`100394 · since 07/02`) | **estimated value is labelled as an estimate, and `not priced` where even an estimate is impossible** — *"a zero would be a claim"* |
| p095 | 20 | | | | Filter bar | `Search` · **`As of 09/11/2026`** (date picker) · `Still held ▾` · `+ Filter ▾` | today the day is silently *"now"* with no control; the picker is also what lets a clerk ask **what was still held at month end** |
| p095 | 20 | | | | Chips | `Why it is here`: All 47 · Never calculated 31 · Calculated and broke 16 ✅ · `Where the fix is`: The read 28 · The account or the plan 13 · The rates 6 · `The reason`: 4 · 3 · 6 · 9 · 19 · 6 · `Age`: Under 14 days 38 · Escalated 9 · Over 60 days 2 | ⚠ **38 + 9 + 2 = 49 over a band of 47**, and the fix/reason groups partition 47 where p040's rule partitions *broke* (16) — `DEF-BIL-5274` |
| p095 | 20 | | | | Bulk bar | `2 selected · ` **`Bill these now`** ` · Change the reason · Release · A catch-up run bills the period they were held in — not this month.` | **`Bill these now` is THE missing control** and is drawn as the least prominent of the three ⚠ |
| p095 | 20 | | | | Columns | `ACCOUNT · PERIOD · WHY IT IS HERE · WHERE THE FIX IS · HELD SINCE · AGE · EST. VALUE` | **two columns the screen exists for**: *why it is here* and *where the fix is* |
| p095 | 20 | | | | Footer | `Showing 47 of 47` | |
| p095 | 20 | | | | ⚠ what is wrong today | **`The screen exists and there is no way out of it.`** The endpoint that bills a held account is built and served; the screen has no button for it, because the list does not choose which run to attach the catch-up to. **`A clerk can hold an account and cannot release it.`** | |
| p095 | 20 | | | | ⚠ pagination | *"Today the screen has **no filters at all**, is **not paged**, and **sorts in memory** — fine at 21 rows, unusable at 400 and **a breach of our own pagination rule**."* | `NFR-3` |
| p095 | 20 | | | | Escalation threshold | **14 days hard-coded as a default** and owed as a tenant setting — *"every utility currently escalates on our number"* | |
| p096 | **20.1 Catch up** | `OLD PERIOD` | `Exists behind S35` | `the catch-up · /:tenant/billing/pending · endpoint served, control absent` | Dialog | `Bill 2 held accounts` — *"Two held accounts will be billed for the periods they were held in. This is a catch-up run, not part of September."* | Q: *"I have fixed these two. Bill them — for the month they were meant to be billed in, not this one."* |
| p096 | 20.1 | | | | Columns | `ACCOUNT · PERIOD IT BILLS · PARENT RUN · WILL BILL` | **it bills the OLD period and says so twice** — in the column heading and in bold on the row |
| p096 | 20.1 | | | | Two periods, two runs | *"A catch-up bills **one period at a time**, never one span covering both."* | stated before committing, with the count on the button |
| p096 | 20.1 | | | | Fields | `Bill date` picker (*"The date these bills carry. Due dates derive from it."*) · `Re-check before billing` = **`Yes — re-price and stop if anything still blocks`** (*"Recommended. A fix that did not take is caught here, not by the customer."*) | defaults to yes |
| p096 | 20.1 | | | | Footer | `Cancel` · `Bill 2 accounts — 2 runs` | ⚠ emphasis inverted |
| p096 | 20.1 | | | | Why the original run cannot be re-run | *"A run is keyed on its cycle and period. Re-running July would be refused as a duplicate of itself — which is exactly why held work needs a catch-up whose key carries **which accounts**. Without this screen those accounts are unbillable for that period, **forever**."* | |
| p097 | **20.2 Hold one** | `RULING OWED` | **`Blocked S37`** | `a standing hold · /:tenant/billing/pending/hold · does not exist in any form` | Dialog | `Hold an account out of billing` — *"This account will be **held out of every bill run** until it is released or the review date passes."* | Q: *"This account is in dispute. Stop billing it until I say otherwise — and do not make me remember to do this every month."* |
| p097 | 20.2 | | | | Fields | `Account` (*"Searchable. One account at a time."*) · `Which services` = `All services` (*"Chips. **All** means every service, including one added later."*) · `Why` (*"From your own reason list. Required."*) · **`Review on` (RED helper: "Required. A hold with no review date is how revenue disappears.")** · `Note` | **All is the absence of a restriction, not eleven ticks** |
| p097 | 20.2 | | | | Money before the commit | `BILLED LAST CYCLE $318.40 · NOT BILLED PER CYCLE ~$318 · BY THE REVIEW DATE ~$955 (3 cycles)` | *"A hold is a revenue decision and should be taken against a figure."* |
| p097 | 20.2 | | | | Footer | `Cancel` · **`Hold this account` (DANGER TIER, red)** | correct |
| p097 | 20.2 | | | | ⚠ the absence | **`There is no such thing today, at all.`** Six account statuses exist and **not one means *billable, but hold the bill***. *Vacation hold* still bills the standing charges; *disconnected* and *pending activation* do not bill at all — and *disconnected* is seeded and nothing assigns it yet. **So a clerk with a disputed account holds it by hand, in every run, forever.** | |
| p097 | 20.2 | | | | **BLOCKED — what is owed from the PO** | *"Whether a standing hold may exist at all, and whether a review date is **required** as drawn or merely offered. Everything else on this screen follows from those two answers."* | **`S37`** |
| p098 | **20.3 Release** | `AUDIT TRAIL` | **`Blocked S37`** | `the release · /:tenant/billing/pending/release · does not exist in any form` | Dialog | `Release 100294 back into billing` — *"This account returns to normal billing from the **next** run. Periods it was held for are billed by a catch-up — **releasing does not bill them**."* | Q: *"The dispute is settled. Put this account back — and show me what we missed while it was held."* |
| p098 | 20.3 | | | | Fields | `Why is it being released?` (*"Required. A hold ending is as recorded as a hold starting."*) · `Bill the held periods now?` = `No — leave them in the queue` (*"Choosing yes opens the catch-up confirm."*) · `Note` | |
| p098 | 20.3 | | | | History | `WHAT HAPPENED · WHEN · WHO · REASON` — Held 09/03/2026 S. Iyer *Billing dispute* · Review date extended 10/12/2026 S. Iyer *Bench test queued* · Released 09/11/2026 you *Dispute resolved* | ⚠ the middle row is dated a month **after** the last; and the hold began 09/03 yet *"3 periods … Jul, Aug and Sep"* were missed. Illustrations, rule 2 — but the COLUMN grammar needs deciding: `WHEN` is the event date or the new review date, not both |
| p098 | 20.3 | | | | What was missed | `3 periods were not billed while this hold was in force — Jul, Aug and Sep 2026, about $955. They stay in the queue.` | *"Stated at the moment of release, which is the one moment somebody is looking."* |
| p098 | 20.3 | | | | Footer | `Cancel` · `Release this account` | ⚠ emphasis inverted |
| p099 | 20.3 | | | | ⚠ the audit-trail limit | *"Where a correction replaces a value, the old value lives only in the audit log — which is pruned on a schedule. Whether these rows are exempt from pruning has never been decided, so **this screen must not be described as a permanent record** until it is."* | hard rule 4's narrowing and **`OQ-1340`**, OPEN |

---

## 6 · The carry-over map (p086–p088), transcribed row by row — and `DEF-BIL-5257` settled

*"Merging three steps into one is the change most likely to drop something quietly, so this
table is one row per element across all six original steps."*
`03 · carry-over` · `No commitment` · `EVIDENCE, NOT WORK` ×3

| # | Element on the six steps | Disposition | Where it lands |
|---|---|---|---|
| 1 | Billing cycle select · Bill date | `UNCHANGED ×2` | Step 1, group **The cycle**. |
| 2 | Step 1's *What this step no longer asks you* panel | `REMOVED` | **Ruled.** It explains why a template picker and a typed due date are absent — a note about a design decision taken long ago, printed to a clerk on every run. Its content belongs in this document. ⚠ *If you want it kept on screen, say so and it returns as a closed disclosure.* |
| 3 | Past runs table | `MOVED` | Step 1, group **Already run for this cycle** — scoped to the cycle being run, with a label, a total, who started it and a way to take over an open one. |
| 4 | The *no actor column, money not served* panel under it | `REMOVED` | **Ruled by fact:** its claim is false — `bill_runs.run_by` exists, is populated and is served as `ran_by`. The money half is true and survives as the honest caveat at step 1's ⑤. |
| 5 | Step 2's six sub-tabs | `MOVED ×6` | Step 2's filter chips, **each with a count**. Three of the six that exist only to explain an unbuilt feature therefore never appear. |
| 6 | Step 2's KPI band — ready · blocked · decisions · silent | `RELABELLED` | Step 2's band in a clerk's words — *Ready to bill · Needs you · Held · Broke · Run total* — and each figure now carries money. |
| 7 | Step 2's per-row facts (meter, this period, average, ratio, threshold) | `UNCHANGED` | Step 2's *What is wrong* cell, written as a sentence with the same figures in it. |
| 8 | Step 2's *base charges are not gathered* cell | `REMOVED` | **Ruled by fact:** false — `gather.py:699-705` gathers base charges through a three-way ladder. |
| 9 | Step 3's 16 case kinds | `MOVED` | Step 2's chips and rows — **the nine the engine actually emits**. The seven that cannot occur are not drawn, and that is the point of the merge. |
| 10 | Step 3's per-row decision select | `UNCHANGED` | Step 2's *What to do* column, with the amount beside it. |
| 11 | Step 3's bulk actions, and the refused waive | `UNCHANGED ×2` | Step 2's selection bar. The waiver stays refused with its reason — **`BR-BIL-060`**, a rule not a gap. |
| 12 | Step 3's *a choice here has nowhere to be recorded* panel | `MOVED` | Becomes a per-row state: a row the server cannot record a choice for says so on the row. |
| 13 | Step 3's *no charges are gathered yet* panel | `UNCHANGED` | Still true — the run produces no late fees or extra charges (`DEF-2596`). Becomes the absence of those two chips: **no chip, no count, nothing to decide.** |
| 14 | Step 4's KPI band — bills · total · left out · broke | `MOVED` | Step 2's band, live from the first paint instead of one step later. |
| 15 | Step 4's three overcharge action words | `RELABELLED` | A real filter chip (*Unusually large 3*) and a real decision control. **They were inert `<span>`s.** |
| 16 | Step 4's *flagged bills cannot be listed* panel | `REMOVED` | **Only once the list exists** — it is honest today (`DEF-2855`). If the list is still unbuilt when this ships, **the panel must stay.** |
| 17 | Step 4's three draft powers panel | `RELABELLED` | Two of the three become working row actions; the third keeps its refusal. |
| 18 | Step 4's per-account retry and hold | `UNCHANGED ×2` | Step 2's row actions. |
| 19 | Step 5's five gate facts | `UNCHANGED ×5` | Step 3. **`BR-BIL-058`** untouched. |
| 20 | Step 5's recomputed totals + the as-at-signing caveat | `UNCHANGED ×2` | Step 3, in one sentence instead of nine paragraphs. |
| 21 | Step 6's *Nothing leaves the building* | `UNCHANGED` | Step 4, word for word. |
| 22 | Step 6's Issue action | `UNCHANGED` | Step 4. |
| 23 | Save & exit | `UNCHANGED` | Steps 1–3. |
| 24 | *Park*, disabled on all six steps | `REMOVED` | **Ruled by fact:** its reason — *"nothing would list it"* — is false; the list is on step 1. Parking is genuinely unbuilt (`PARKED_HOME_PATHS` has no `bill_run` member), so **a control that cannot work and gives a false reason is worse than no control.** When parking is built it returns. |
| 25 | The six-tab Billing strip in the wizard header | `UNCHANGED` | Kept — it is how a clerk leaves sideways. |

### The settlement

**Counting the ROWS, with their `×N` multipliers:**

```
UNCHANGED   rows 1(×2) 7 10 11(×2) 13 18(×2) 19(×5) 20(×2) 21 22 23 25  =  20
MOVED       rows 3 5(×6) 9 12 14                                        =  10
RELABELLED  rows 6 15 17                                                =   3
REMOVED     rows 2 4 8 16 24                                            =   5
                                                                   TOTAL = 38   ✅
```

**The summary block printed on p088 says:**

```
Elements across the six steps   38
  unchanged   19
  moved        9   -> 6 sub-tabs become chips · decisions · bands · retry/hold
  relabelled   4   -> the KPI words · overcharge actions · draft powers
  removed      5
Elements in the four steps      47   = 38 - 5 removed + 14 new
```

**19 + 9 + 4 + 5 = 37, not 38.** The summary block does not add up to its own total, and
three of its four components are wrong. **Settled from the rows, as `DEF-BIL-5257` requires:**

> **38 = 20 unchanged + 10 moved + 3 relabelled + 5 removed.**

Where the summary went wrong, precisely: it lists *retry/hold* as MOVED where row 18 marks it
`UNCHANGED ×2`; it omits the past-runs table, which row 3 marks `MOVED`; and it claims four
relabelled while naming only three, which is the number the rows carry. The trailing
arithmetic `38 − 5 + 14 = 47` is **correct**, and the fourteen new elements reconcile only if
*3 defaults* is counted as one element: scope · sweep-up · defaults · label · open-run
takeover · search · chips-with-counts · Amount column · plain-words cause · link-out to fix ·
re-price · pagination · reconciling count · print door = **14** ✅

**And the removals carry their own footnote, which a builder needs:**
> `** FOUR OF THE FIVE REMOVALS ARE THINGS THIS DOCUMENT PROVED FALSE, not things somebody
> decided to drop. The fifth is conditional and says so. **`

---

## 7 · BUILD THIS · Blocked · never built

### The two `BUILD THIS` bands in §03

| Entry | Band | Closes |
|---|---|---|
| **16 Scope** | `BUILD THIS · New build · "Two inputs become five groups, and pricing starts here"` | `BIL-S24` · `BIL-S25` · `DEF-106` · `DEF-1084` |
| **17 Check** | `BUILD THIS · New build · "One screen, priced, filterable, decisions inline"` | `BIL-S26` · `BIL-S27` · `BIL-S28` |

### Everything §03 marks `Blocked`, and the reason each gives

| Entry | Blocked on | The reason, in the document's words |
|---|---|---|
| **16 Scope** | `S89` | *(the blocked commitment named in the entry band)* |
| **20.2 Hold one** | `S37` | *"Whether a standing hold may exist at all, and whether a review date is **required** as drawn or merely offered. Everything else on this screen follows from those two answers."* |
| **20.3 Release** | `S37` | the same ruling — a release cannot be specified until a standing hold is |

### Commitments §03 mints or names

`BIL-S24` `BIL-S25` `BIL-S26` `BIL-S27` `BIL-S28` (closed by 16 and 17) · **`BIL-S38`** (the
run key does not carry the service scope) · **`BIL-S39`** (per-connection: a line set, a
tariff resolution and a plan snapshot per connection, and the tier ladder resets per
connection) · **`BIL-S50`** (a specimen rendered from priced data at sign-off) · `S27` `S83`
`S90` `S91` `S92` `S96` `S73` `S38` `S95` `S46` `S42` `S43` `S44` `S39` `S50` `S77` `S102`
(new-build flags) · `S89` `S37` (blocked).

### What the document says about itself that a builder must carry

* **Every drawing in §03 is `REDESIGN` and `NEVER BUILT`.** Today the product ships a
  **six-step wizard, screens 04–09 in §17**.
* **17.0 does not exist**, and *"at 25,000 accounts it is the difference between a usable
  product and an unusable one."*
* **`Estimate from history` refuses today** — the server wants a quantity and a unit and no
  screen has ever sent them. 17.16 and 17.22 are both built on it. *"No defect row."*
* **The engine does not raise a late-fee case at all**, so 17.20 may be reachable only after
  that is fixed. *"It is drawn now because the refusal is law either way."*
* **`flagged bills cannot be listed` must STAY on screen** if the list is still unbuilt when
  this ships — *"flagged so nobody drops it by following the drawing."*
* **The held queue has no filters, no pagination and sorts in memory** — a breach of `NFR-3`.
* **The run is keyed on tenant + cycle + period**, so screen 1 shows scope and does not
  choose it (`BIL-S38`). *"Zero rows in the register mention the scope field."*
* **No screen in the product shows units and accounts together**, and the gap between them is
  where every master-account failure lives.
* **The audit trail is not a permanent record** until `OQ-1340` is answered.

---

## 8 · Every PO ruling quoted on a §03 page

| Date | Verbatim | Where | What it decides |
|---|---|---|---|
| 2026-09-11 | *"our idea is to show all the data to billing clark before submitting the bill run - it kind of allow him to do all decision before hand, see the data correct the data and then submit it so that billing errors are reduce sbtantially"* | p028 | the run-intent ruling — the whole of §03 |
| 2026-09-11 | *"between step 1 and step 2 - we are basically running pre bill checks and it is not actual bill generation"* | p033 | 17.0 exists; money does not exist until sign-off |
| 2026-09-11 | *"all dates should be date picker, all drop down should be drop down, all search should be search and multi select, with all as option available"* | p030 | every control on these screens |
| 2026-09-11 | *"per conenction"* | p093 | base charge and tier ladder are per connection |
| 2026-09-11 | *"as per connection"* | p093 | taxes, fees, discounts and the plan snapshot are per connection — **reverses the 2026-08-11 *"Tax rates are for bill not for service"*** |
| 2026-09-11 | *"if not use thats okay we will lose it; its okay; dont over complicate"* | p033 | an unused bill number is lost |
| 2026-09-12 | *"if clark say 231 then all 231 should be actioned"* | p042 | a chip-wide selection is a pinned snapshot, actioned in full |
| 2026-09-12 | *"you can calculate it on screen - in such case we will have to show work in progress to clark"* | p043 | the on-screen-calculation ruling — 17.22's progress line |
| 2026-09-11 | *"we will use Utility Service Chip E, W, G"* | p031 | service badges are two-letter chips, not `name[0]` |

---

## 9 · Contradictions found — every one filed, none chosen silently

Eleven new defect rows were filed with `10-scripts/file_defect.py --id-module BIL`. Two were
already on the register and are settled above rather than duplicated.

| # | Id | What contradicts what | How this inventory settles it |
|---|---|---|---|
| 1 | **`DEF-BIL-5272`** | 17.L3's meta line says `4 bands · 15 chips`; its annotation says *seven bands, twenty-six tags*; the drawing shows 7 and 26; p053's table gives a fourth reading and p054–55 a 15-row inventory | **26 tags in 7 bands** is the strip (§3). The 15-row table is the **drill-in list** (§4), with the three label corrections applied |
| 2 | **`DEF-BIL-5273`** | p041 and p046 say the Needs-you tags must sum to **more** than the band (12 accounts, 19 case rows); both drawn strips sum to **exactly** the band | **The rule is the specification.** A tag counts CASES, a band counts ACCOUNTS; the built strip must not assert equality. The drawn figures are illustrations |
| 3 | **`DEF-BIL-5274`** | Screen 20's age chips sum to **49** over a band of **47**; its fix/reason groups partition 47 where p040's rule partitions *broke* (16) | **Unsettled and needs a decision**: `Over 60 days` is a subset of `Escalated` on screen 20 and a third disjoint band on the Check frames. Pick one and write it into the component contract |
| 4 | **`DEF-BIL-5275`** | 17.11 draws `AT RISK $0.00` against its own *"Never $0.00 — a zero here would be a claim"* | **The annotation wins.** `not priced`, never `$0.00`; the built column has no zero path |
| 5 | **`DEF-BIL-5276`** | 17.21 draws a **fifth** KPI cell and **two extra** toolbar controls against *"a filter never changes these four cells"* and *"the toolbar is the same on all twenty-nine frames"* | **Needs a decision before the strip is built as a shared component** — it is a prop contract, not a per-screen choice |
| 6 | **`DEF-BIL-5277`** | 17.22 draws `Type 231` / `Action all 231`; its annotation says the button counts **198** and you type **198** | **The PO ruling wins over the annotation** — *"if clark say 231 then all 231 should be actioned"*, and the dialog body agrees. The annotation is the stale half |
| 7 | **`DEF-BIL-5278`** | Six dialogs (17.16, 17.18, 17.19, 17.22, 20.1, 20.3) draw **Cancel boxed and the commit ghosted**, inverting p077's own footer rule. 17.17 and 20.2 draw it correctly, in the danger tier | **B14 rules 37 and 38.** Cancel is the ghost on the left; the commit is on the right and names the act and the count |
| 8 | **`DEF-BIL-5279`** | `Showing 50 of 44` (17.8) · `Showing 4 of 4` over three rows (17.1) · `Showing 11 of 11` over four (17.15) | Footers are server figures, never drawn literals. All three recorded as illustrations |
| 9 | **`DEF-BIL-5280`** | p052's reconciliation says *"21 held by your defaults, 0 broke"*; the KPI on the same frame says *"15 by a default · 6 blocked"* | **15 / 6.** The sentence must be generated from the four cells it reconciles |
| 10 | **`DEF-BIL-5281`** | p092's spec text says *"3 of the 11 cannot be billed today"*; the screen-16 drawing and 17.15 say **1**, post the 09/11 ruling | **1.** The master line is a query, not a typed sentence |
| 11 | **`DEF-BIL-5282`** | 17.14 Ready draws a header checkbox and row selectors against its own *"no selection boxes"* and p042's *"no selector where nothing can be actioned"* | **No selector on 17.14.** p042's *"twenty-eight of twenty-nine"* should read twenty-seven |
| — | `DEF-BIL-5257` *(already filed)* | The carry-over summary block and its own rows; one Held chip count between p051 and p053 | **Settled in §6: 38 = 20 + 10 + 3 + 5** |
| — | `DEF-BIL-5269` *(already filed)* | The drawing's stage numbers are one behind `pipeline.py` | **Settled in §0 rule 4** — both numbers given on every row |

### Smaller divergences, recorded and NOT filed — B14 rule 37 settles them

Every one is a drawn figure or a drawn name, and rule 37 says a figure in a wireframe is an
illustration. They are listed so the next lane does not re-find them and mistake them for
findings.

* Account **100251**'s ratio reads `4.2×` on the five layer frames and `4×` on the settled
  frame 17. The arithmetic (31 ÷ 7.4 = 4.19) supports **4.2×**.
* Account **100302** is *Hillcrest Apartments* (E W, $70.17) on 17.L1–L5, 17.15 and 19, and
  *D. Whitfield · 8 Kiln St* (W, 12 kgal) on p052's fourth row.
* Account **100418** is *Nakamura, S. · 7 Quarry Rd* on 17.8 and *Harbourgate Motors · 3 Dock
  Rd* on 17.21 and screen 18.
* Account **100288**'s *what is wrong* is *"No base charge covers this customer type"* on the
  main Check frame — which is a **Held reason**, not a Needs-you case — and *"Trash is billed
  per cart and no cart count is recorded"* on 17.12.
* Screen 16's step line is *"nothing has been **created** yet"* in the drawing and *"nothing
  has been **written** yet"* in the p035 zone sketch; its commit button is `Check this run →`
  in the drawing and `Prepare` in the sketch.
* *"Pro-rate by days"* (screen 16) vs *"Prorate to the cycle's days"* (17.5).
* p041 says *"all **thirty** frames"*; p043 says *"all **twenty-nine**"*. **29 is the count
  that reconciles**: 17.L1–L5 (5) + 17.0 + 17 + 17.1–17.22 (22).
* p031's service-badge table orders Broadband **6th**; the platform seed (CLAUDE.md, eleven
  services) has it **8th**. The colours and the eleven names agree.
* 20.3's history table dates *Review date extended* (10/12/2026) after *Released*
  (09/11/2026), and attributes Jul and Aug to a hold placed 09/03. The `WHEN` column's
  grammar needs deciding; the dates themselves are illustrations.

---

## 10 · What a build wave takes from here

1. **Build the shape, never the figures.** Every number in §5 is an illustration.
2. **The band strip is one generated component**: 7 bands, 26 tags, ordered by obligation,
   band totals count accounts and tags count cases.
3. **The KPI strip is four cells on the settled frame and five in flight** — and whether it
   gains a fifth for `In arrears` is `DEF-BIL-5276`, unanswered.
4. **Stage numbers: add one from drawn stage 5.** Nothing money-bearing exists before code
   stage 7.
5. **Two entries are `Blocked` on `S37`** and cannot be built until the PO answers whether a
   standing hold may exist and whether its review date is required.
6. **The `flagged bills cannot be listed` panel must stay** unless the list ships first.
7. **Read §9 before writing a line.** Eleven of the contradictions there would otherwise be
   built as drawn.
