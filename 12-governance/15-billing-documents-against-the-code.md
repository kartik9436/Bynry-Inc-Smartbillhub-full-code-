# The two billing documents, checked against the code, section by section

**31 August 2026 · read at version 2.108.0 · every section of both documents · the first time this has been done.**

You asked to be sure the two documents are actually implemented. This is the answer, one row per
section, and nothing is left out. Forty sections were checked: twenty-nine in *Bill Generation
Logic*, eleven in *The Bill Run*.

**The short version. Thirty-two sections describe something the product genuinely does. Six describe
something it does not. Two were deliberately left unbuilt and there is a ruling for each.** Six
defects have been filed for the gaps, and one more for something the audit found on the way.

**And there is a second answer that matters as much as the first.** Nine sections describe gaps that
have since been closed — the documents are more pessimistic than the product. The most important of
those is the minimum charge, which both documents call the largest single hole in the billing engine.
It was built on 30 August. If a plan is being made from these documents, it is planning work that is
already done.

**The counts, so they can be checked against the tables below.**

| | Built | Not built | Deliberately not | total |
|---|---|---|---|---|
| Bill Generation Logic | 27 | 1 | 1 | **29** |
| The Bill Run | 5 | 5 | 1 | **11** |
| | **32** | **6** | **2** | **40** |

**Reconciling the tables to those numbers**, so nothing has to be taken on trust. The bills
table draws 39 rows for 29 sections. Section 06 is drawn as three rows — one per split it
describes — and counts once as a section; two of its three are built and the third is not,
so the section is counted **not built**. The other eight extra rows are lettered *a* and *b*:
they are not sections but each section's own warnings, pulled out and judged separately,
because seven of the eight are where the documents have gone stale. The run table draws one
row per section, eleven for eleven.

---

## How to read the verdict column

**Built** means the code does what the section says, and the row names the line that shows it. Not
the absence of a fault — the line. An audit that concludes "built" because it could not find the
fault concludes that for everything, including the places it looked in the wrong file.

**Not built** means the section specifies something the product does not do. Every one has a defect
filed.

**Deliberately not** means there is a ruling saying so, and the row names it.

**The last column is the one worth your attention.** A rule can be correctly implemented and still
silently wrong, because nothing compares it. That is not a theory — it happened this month. The tax
step existed, passed its tests, and dropped a restricted state tax from every commercial account of
every utility. It surfaced the hour somebody built a comparison for it, and not before. So every
section that can change money or stop a bill carries a second verdict: **is anything checking it
against an independent answer, or only against itself?**

Three things in this product do real comparison: the frozen reference figures replayed through the
engine, the two pricing paths run side by side and diffed, and a handful of purpose-built scripts
that price the same account twice under different rules. Everything else is a test that asserts what
the code already does — useful, but it cannot catch the tax error, because the tax error passed all
of those.

---

## Bill Generation Logic — twenty-nine sections

| # | Section | Verdict | The line that shows it | Compared? | Ids |
|---|---|---|---|---|---|
| 00 | The eight layers, and what each one decides | **Built** | The stage order is declared once as data, in `rating/pricing/stages/__init__.py:63`, and the eight layers map onto it | **Yes** — a test asserts the running pipeline and that list agree | — |
| 01 | The status branch — six ways this can go | **Built** | Four behaviour classes at `customers/services.py:275-278`; billing reads them at `billing/stages/resolve_subscription.py:59-62` and branches at `:106` | Tests only | — |
| 01a | *…and the caveat: a cut account is billed in full* | **Now false** | A cut writes the disconnected status at `customers/disconnects.py:3478`, called from the commit at `:3765`. Fixed 30 August | Tests only | — |
| 02 | What the account hands to the bill | **Built** | All eight facts resolve; the three the document warns about are all now built (below) | Tests only | — |
| 02a | *…the template is resolved once per run, not per account* | **Now false** | The account's own override and its category are read per bill at `billing/issue.py:1621-1633` | Tests only | — |
| 02b | *…email and text preferences are designed and unbuilt* | **Now false** | Both are real columns: `customers/models.py:449` and the text preference beside it | Tests only | — |
| 03 | How long is this bill for | **Built** | The day-span judgment belongs to the run, at `billing/read_analysis.py:108`, and is one of the categories at `:113` | Tests only | — |
| 03a | *…and the surface that shows a clerk this does not exist* | **Now false** | It is served through `billing/selectors.py:2943` and drawn as a case on the review step at `billRunShared.tsx:590` | Tests only | — |
| 04 | The per-service loop, and its seven questions | **Built** — all seven | Which schedule and what shape refuse at `rating/resolution.py:170` and `:176`; the connection size at `:187`; a missing reading at `billing/stages/measure_consumption.py:409`; the multiplier and the count at `resolution.py:252` and `:263`; the unit check at `rating/pricing/stages/normalize.py:83-84`; the pricing itself in the stage beside it | **Four of seven only.** Which schedule, what shape, the size and the quantity are each a step of the side-by-side comparison. **Three are not: what shape the schedule is, whether we have a reading, and whether the unit matches.** Those three are implemented and nothing compares them | already known |
| 04a | The six rate shapes | **Built** — all six | All six are registered together at `rating/pricing/models/__init__.py:84-89`, and the catalogue is sealed at start-up (`registry.py:70`) so nothing can add one later | **Yes** for flat, tiered and the multiplier — frozen figures replayed through the engine | — |
| 05 | Three services, side by side | **Built** | The reference bill is replayed through the engine by the frozen-figure tests for the flat and tiered shapes | **Yes** | — |
| 06A | Case A — the service starts or ends mid-period | **Built** | One factor, calendar days, rounded once, at `rating/engine.py:496-511` | **Yes** — a frozen figure runs through the engine | — |
| 06B | Case B — the rate changes mid-period | **Built** | The period is cut at every rate-version and plan boundary by `billing/midperiod.py:222` | Tests only | — |
| 06C | **Case C — the season changes mid-period** | **NOT BUILT** | The time-of-use model says it in its own words at `rating/pricing/models/tou.py:75-79`: *"It does not span two seasons."* One season is resolved for the whole period and every day is priced at it. The boundary finder at `midperiod.py:222` cuts at rate changes and plan changes and **not at a season change** | **No** — and there is no frozen check for it either | **DEF-2840** |
| 07 | When the consumption is not enough — the minimum charge | **Built** — *the document says this is the largest hole in the engine, and it was closed on 30 August* | The per-service floor and the whole-bill floor are both at `rating/pricing/stages/apply_charges.py:178` and `:255`, wired into the engine at `engine.py:146-149` and `:464-467`, and the two thresholds now travel the interface at `pricing/contracts.py:335` and `:340` | **Yes** — a frozen figure, and a deliberate tamper case that proves the check can go red | — |
| 08 | The base charge, and how it differs from usage | **Built** | It prorates at `engine.py:511`; it sits inside the tax base by the kind of the line, not a tick-box; it comes from the charge catalogue, not the rate schedule | **Yes** — a purpose-built script compares where the base comes from on both paths | — |
| 09 | Walking the charge codes, one at a time | **Built** | Both doors at `rating/resolution.py:1470` and the conflict refusal at `:1497`; the four filters are the charge-code step of the chain | **Yes** — that step is compared account by account | — |
| 10 | Discounts — six rules, in the order they bite | **Built** | Proof, exclusivity, precedence and the budget are all carried at `rating/discount_pricing.py:221-234`; both subtotals are handed on at `:280-281` and filled at `:555-556`, which is what lets each authority take the one its own law names | **Partly** — selection is a compared step; the arithmetic is tests only | — |
| 11 | Taxes — one pass, one base, no tax on tax | **Built** | One place turns a rule into a number, at `rating/pricing/stages/compute_tax.py:355-384`; exemption zeroes the whole bill at `:121` | **Yes, and only since this month** — this is the step that was silently dropping a state tax. It now has both a comparison run and a script that prices the same account twice | — |
| 11a | *…per-unit taxes are not built* | **Now false** | The third form is there at `compute_tax.py:371-376`, marginal above a stated quantity, with the unit checked and never converted | **Yes** | — |
| 12 | Layer 6 — payments received, and the credit this bill spends | **Built** | Credit is drawn at issue and reported at `billing/issue.py:2447`; it comes back as *nobody could ask* rather than zero (`:628-631`); readings move to billed at `:2090` | Tests only | — |
| 13 | Layer 7 — the last bill, and what is still owed | **Built** | The three figures are stamped once at `billing/issue.py:1516`, blank rather than zero when unanswerable, and a migrated opening balance moves on both sides at `billing/payments_seam.py:632-674` | **Yes** — the opening entry is a frozen figure run through the engine | — |
| 14 | Putting it on a page | **Built** | The page is rendered before the status moves and a failed render refuses the issue, at `billing/issue.py:82`, `:157` and `:322` | Tests only | — |
| 15 | Two kinds of bill — the ordinary one and the landlord's | **Built** | Occupancy is asked fresh each run; the empty units are priced at `billing/gather.py:959`; the three coverage refusals at `:121-130`. The two money questions the section leaves open are still genuinely open | Tests only — five test files | — |
| 16 | Sub-meters — the master meter and what hangs off it | **Built** | The reconciliation has its own tables, added by the two migrations named `submeter_reconciliation`. Nothing bills the gap, exactly as the section says | Tests only | — |
| 17 | What is on the printed page, and what is still blank | **Built** | Everything the section lists as stamped is stamped, and what it lists as missing is genuinely missing: no logo, no colour, no barcode, no plotted graph (`billing/documents.py:498-510`) | Tests only | — |
| 17a | *…the twelve-month history is not on the bill* | **Now false** | Twelve months are frozen onto the bill at issue by `billing/issue.py:1545` and printed as a table at `documents.py:1279`. Built 31 August | Tests only | — |
| 17b | *…the bill message and ways to pay are empty* | **Now false** | Both are read from the pinned template at `billing/issue.py:1533-1534` and printed at `documents.py:1165-1169`. Built 30 August | Tests only | — |
| 18 | Where the eight layers stand | **Built, and now the most misleading page in either document** | Every capability its left-hand column claims is real. **Its right-hand column — what is not working — is wrong in six of its eight rows**, and its closing "if you fix three things, fix these" names three things that are all now built | — | — |
| 19 | The approval gate — five facts, nothing goes out unsigned | **Built** | Four mandates recorded separately at `billing/release.py:247-250` plus the final confirm at `:573`; issue is refused without them | Tests only — three test files | — |
| 20 | Delivery — four channels, no provider behind any | **Built, including the gap** | The queue, the scheduling and the de-duplication are real; the absence is real too and stated in the code — *"No provider adapter exists for ANY channel"* at `notifications/dispatcher.py:57` | — | — |
| 21 | Getting paid — autopay, and the question worth money | **Built, including the gap** | The intent carries the gross and says so by name at `billing/issue.py:548-550`; nothing is captured. The open question is genuinely open and correctly reported rather than quietly decided | Tests only | — |
| 22 | Seven kinds of bill | **Built** | Exactly the seven named, declared together at `billing/models.py:160` | **Partly** — two of the seven have frozen figures | — |
| 23 | Changing a rule without opening the engine | **Built** — one claim slightly overstated | The usage stage names no shape and a test greps it for that; the catalogue refuses registration after start-up at `registry.py:70`; the stage order is data with a test. **The claim that there is exactly one rounding call is not literally true** — there are two, at `pricing/stages/finalize.py:73` and `engine.py:511` — but they sit on separate paths and each rounds once, so no amount is ever rounded twice. The comment at `finalize.py:24` asserting it is the only one is stale | **Yes** — three of the four are enforced by tests that fail rather than conventions that are offended | — |
| 24 | A formula written by the utility, not by us | **Deliberately not** | Your ruling of 31 August: *"We dont have to implment it right now."* The document already marks it a proposal rather than signed law. Nothing should be built here until a real utility needs a rule the product cannot otherwise express | — | ruling recorded |
| 25 | One bill is not one record | **Built** | Header, lines and a frozen document, with the template pinned as two plain columns rather than a link | Tests only | already known |
| 26 | Nothing runs in the browser | **Built** | All three heavy steps have background job kinds registered at `billing/run_jobs.py:147-150` and handlers wired at `:657`. Both things the section says are missing — the worker and re-opening a run — are now done | — | already known |
| 27 | How the code is divided — six rings | **Built, with seven exceptions and nothing guarding it** | See the section below — it deserves more than a row | **No** — nothing anywhere checks it | **DEF-2845** |
| 28 | The endpoints | **Built and grown** | Eleven run routes now, not nine. Three of the four the section says must be added are built: reading one run back (`billing/api.py:1795`), reading its break list (`:1802`), and the job poll that already existed | — | — |

---

## The Bill Run — eleven sections

This document is mostly a **proposal**, not a description, so the verdict answers a different
question: has the proposal been built?

| # | Section | Verdict | The line that shows it | Compared? | Ids |
|---|---|---|---|---|---|
| 01 | As it is — the six screens | **Built** as a description of the wizard | Six steps, five phases, the case tables and the gate all render as drawn. Three of its "not built" notes have since been closed | — | — |
| 02 | As it is — the process | **Built** | Seven stages in one fixed order; the first five write nothing, which is what makes the review step safe to refresh | **Yes** — a test asserts the pipeline matches the declared order | — |
| 03 | As it is — the endpoints | **Built — and its headline finding is now closed** | The document's biggest conclusion was that a run cannot be re-opened. It can: the route is mounted at `billing/api.py:1795`. Two routes still have no screen calling them | Partly | **DEF-2843** |
| 04 | As it is — the database | **Built** | Four tables became six. The break list is now a real table (`billing/models.py:437`), and a catch-up run has its parent link (`:294`) | — | — |
| 05 | First pass — seven proposals from the screens | **Not built** — three of seven done | Storing the breaks and moving the work to the background are both done. **Four are outstanding**: the three draft powers, the authorisation export, the catch-up run, and the pricing comparison | — | **DEF-2841, DEF-2842, DEF-2843** |
| 06 | The requirements — what was actually asked for | **Not built** — four named requirements are still unmet | Six of its own verdicts have moved, all in the good direction. **Four have not**: the three draft powers, the authorisation export, the category breakdowns beneath the summary, and the sign-off figures. These are confirmed rules rather than opinions, so the honest verdict is that the product does not yet do what was signed off | — | **DEF-2841, DEF-2842, DEF-2844** |
| 07 | The gap check | **Built** as a method | Its conclusions were right, including the one it found only by reading the requirement rather than the screen. That finding has since been fixed | — | — |
| 08 | The revised proposal | **Not built** — proposals, and you have ruled on which to pursue | Your ruling of 31 August: pursue the first, second, fourth and seventh; hold the rest. The scenario screens beyond the interrupted run are still undrawn | — | ruling recorded |
| 09 | The tasks and the waves | **Not built** — the first wave landed | Re-opening a run was the first wave and it is done. The sign-off figures were the second and they are not | — | **DEF-2844** |
| 10 | All the billing changes, wired into one plan | **Not built** | A plan, and it should be re-cut: nine of the gaps it sequences are already closed | — | — |
| 11 | The prompt — run this analysis on any process | **Deliberately not** | A reusable prompt. There is nothing here for the product to implement, by its own design — it is the method, not a requirement | — | — |

---

## The six rings — the structural claim, tested

The document says every file in the billing module sits in exactly one of six rings and calls only
inwards, and it calls the counts measured rather than estimated. Two of the six were tested earlier
this month and held. **The rest are tested here.**

**The shape holds.** Every file in the module does sit in one ring, and the ring names map cleanly
onto how the directory is actually laid out. Two claims that had never been tested both hold
exactly:

* **The table ring computes nothing.** Zero methods and zero derived properties across all three
  model files — not one. A model that calculated would be a pricing rule hiding in the schema, and
  there is not one.
* **The read ring writes nothing.** No database write anywhere in it. The two lines that look like
  writes are dictionary updates.

**The counts have drifted, and only one still matches.** The outward-facing ring is still five files.
Everything else has grown: the service ring from 37 files to 44, the read ring from 17 functions to
42, the seam ring from 8 files to 9, the table ring from 10 tables to 16. That is ordinary growth,
not a fault — but "measured, not estimated" only stays true if somebody measures again, and nobody
has until now.

**One rule is genuinely broken.** The seam ring is described as the only door to other modules —
*"Nothing else crosses."* **Seven imports in five files cross anyway.** Three are demo-data seeding
and are the least worrying. The sharpest is in the read ring, which reaches directly into another
module's tables; because the read ring is the layer two screens share, a disagreement introduced
there is a disagreement between screens.

**And nothing enforces any of it.** There is no check anywhere in this repository that reads which
module a billing file imports, or which ring a function sits in. The nearest two checks ask whether a
seam has an implementation and whether a module is invisible from the outside — neither asks whether
a seam was *bypassed*. So the structure is true by habit. It degrades one import at a time, and
nothing goes red when it does. **That is worth recording either way, and it is why the seven
exceptions above went unnoticed: not because anyone ignored a warning, but because there was never
a warning to ignore.**

---

## What is not built — the whole list

Six things, in the order I would fix them.

1. **The sign-off screen still cannot say how much money is about to be billed.** Three of the four
   figures render as "not available", and the server computes all four. This is the screen where a
   clerk authorises a thousand bills. *(DEF-2844)*
2. **A period that crosses a season boundary is priced entirely at one season's rates.** No split, no
   warning, and a bill that adds up perfectly. The document works this case in full, with a total, and
   draws it as built. *(DEF-2840)*
3. **The three things a clerk may do to a draft — exclude it, re-rate it, add a line to it — do not
   exist.** They are drawn on the screen, switched off. They are the only legitimate ways a draft may
   change. *(DEF-2841)*
4. **Holding an account has no drain.** The catch-up run has a route and a client function and no
   screen calls either, so held accounts collect in the pending queue and nothing bills them. The
   pricing comparison is unreachable the same way. *(DEF-2843)*
5. **There is no way to read back what was approved.** You chose an export rather than a screen. The
   screen was correctly not built; the export was never built either, so the only record of what was
   authorised has no reader. *(DEF-2842)*
6. **Seven imports bypass the module boundary, and nothing would ever tell us.** *(DEF-2845)*

---

## What the documents now overstate

Nine gaps described in the two documents have since been closed. This matters because both documents
are being used to plan from, and **planning from them today would fund work that is already done.**

The minimum charge · the disconnected status · the per-account template · email and text preferences ·
per-unit taxes · the twelve-month history · the bill message · ways to pay · re-opening a run.

Every one is dated, and every one has its line in the tables above. The largest is the minimum
charge, which both documents call the biggest single gap in the billing engine.

---

## One more thing the audit found

**The figure everybody quotes for the billing maths does not check the billing engine.** The harness
that reports thirty-three of thirty-three reads the *documents* and confirms their arithmetic is
self-consistent. It says so plainly in its own opening lines — it is deliberate and it is honest. But
it is quoted alongside the sentence naming the sixty-one frozen figures as the billing contract, and
that pairing reads as though the engine were checked against all sixty-one.

What actually runs the engine against a signed figure is a separate set of fifteen tests, covering
fifteen of them. **So roughly three quarters of the signed billing figures have no test that runs the
engine.** The widely quoted number cannot go red when the engine drifts — only when a document
contradicts itself. *(DEF-2846)*

---

## The method, and the proof it could return a negative

For each section: take its specific claims, find the line that implements each, read the surrounding
code to confirm it does what the section says, and cite it. Then ask separately whether anything
checks that behaviour against an independent answer.

**A verdict that cannot fail is worthless, so the method was tested against things known to be
missing before it was trusted.** Three checks:

* **The unit-match question**, known to be implemented but absent from the comparison chain. The
  method found the implementation and found no comparison step for it — the right answer, both halves.
* **The missing-reading question**, the same, and the same result.
* **The minimum charge**, which both documents call the largest hole in the engine. The method was
  run against it blind and returned **built** — correctly, because it was built on 30 August. That is
  the more useful test of the two: it proves the method reads the code rather than the document.

The method then returned **not built** on its own, unprompted, for the season split — a section both
documents present as working. That is the negative it was built to be able to return.

**What this audit did not do: it changed nothing.** No fix, no build, no edit to either document.
Six defects filed, one record written, and every verdict traceable to a line.
