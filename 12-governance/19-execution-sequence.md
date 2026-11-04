# 19 · The execution sequence — what we are doing next, and why in this order

**PO-approved 2026-08-27**, verbatim: *"Okay - I'm good with your suggestion and execution chain - please
proceed once existing agent finish"*, and *"Can you write down this sequence in repo so that we don't lose it
in chat"*.

## ⚠ WHY THIS IS A FILE AND NOT A CHANGE REQUEST

The PO asked whether this needs a CR. **It does not, and `13-change-process.md`'s own classification table is
the authority** — its seventh kind reads *"Process change → decision log + the process file"*. A change request
exists for when the **agreement about the product** changes; nothing about the product changes here, only the
order we work in. Filing it as a CR would do exactly what that process warns against: *"A change register full
of things that were really our mistakes tells you nothing about the product."* The same is true of a register
full of plans.

## ⚠ AND WHY IT IS NOT ONLY IN THE DECISION LOG

The reasoning IS in `02-decision-log.md` (2026-08-27, *"THE ORDER TO FINISH IN, FROM CR-038 ONWARD"* and
*"HOW TO PRIORITISE THIS REGISTER"*), and that is where it belongs — the log is **append-only**, so it holds
*why* permanently and correctly.

**But you cannot tick a box in an append-only file.** A sequence people work from needs state that changes.
So this file mirrors the split the repo already uses between `01-open-questions.md` (live, statuses updated in
place) and `02-decision-log.md` (append-only reasoning): **the log holds the WHY, this file holds the WHERE WE
ARE.** Update the State column here; never rewrite the log.

## THE MEASUREMENT THIS RESTS ON

⚠ **THE FIGURES BELOW REPLACE THE ONES THIS SECTION SHIPPED WITH, AND THE OLD LINE IS `DEF-1784`.** It read
*"955 defects, 354 open — 4 critical · 90 high · 146 medium · 114 low"*, and **three of its four cells were
wrong while the row added up to 354**: the `90` was the corrected post-normalisation high, the `146` was the
*pre*-normalisation medium, and `114` was neither reading of low. A total that foots reads as a figure that
was computed, which is why it survived a check. This file's own step 5 is about exactly that.

Re-measured after the severity collapse, **2026-08-27**, and **the definition is stated because the two
readings differ by 14**:

| open means | total | critical | high | medium | low |
|---|---|---|---|---|---|
| `open` + `reported` + `fixed-in-part` + `partially-fixed` | **353** | **4** | **89** | **176** | **84** |
| `status == "open"` alone | 340 | 4 | 83 | 171 | 82 |

**960 rows on file, measured at the END of the commit that carries this table** — after `DEF-1710`,
`DEF-1711`, `DEF-1785`, `DEF-1786` and `DEF-1787` were all filed or closed. **The state is stated because
this table was re-measured four times while being written and moved every time**: filing and closing rows
shifted three of its cells without changing the total, which is the same illusion `DEF-1786` was filed for.
A count is true at a state or it is not true.

CR-038…046 are done or in flight. **12 of the 93 open critical+high were filed on 2026-08-27 alone** (this line said *13 of the 94* and both halves were re-measured rather than carried, which is `DEF-1786`'s whole lesson), so the
register is still being discovered, and *sequencing* matters more than throughput.

**Quote the definition with the number, every time.** Half of what went wrong with the old line was that
nobody could tell which of these two columns it came from.

## THE SEQUENCE

| # | What | Why it is here and not lower | State |
|---|---|---|---|
| **1** | **The four criticals, as ONE job** — `DEF-438` · `DEF-498` · `DEF-493` · `DEF-652` | All four are the R1–R7 rating chain. `DEF-438` (the chain has **no production caller at all**) is almost certainly the root and the two R4 defects its symptoms — a chain nothing calls is a chain whose narrowing nobody has exercised. **This is the billing engine; nothing else matters as much.** Four tickets would pay the diagnosis cost four times | 🟡 **STEPS 1–3 DONE · **STEPS 4–6 UNBLOCKED 2026-08-27**. The metering lane landed `assets.Asset.size_class` (`DEF-514`, `DEF-1811`, `DEF-1812` all fixed) and the shadow's own measurement moved on the same fixture through the production adapter: **`attempted 0 · blocked {connection_size_unresolved: 1}` → `attempted 1 · disagreed 1 · chain_refused 1 · by_step {R4: 1} · blocked {}`.** ⚠ **`by_step {R4: 1}` is `DEF-498`'s finding arriving as a measurement off real rows for the first time**, and `disagreed` is **1 rather than 0**, which is the proof the multiplier was not defaulted — defaulting it would have reported parity by construction. **The vocabulary needed no question: `BR-TEN-170`/`171` were already PO-ratified**, so `OQ-900–909` were returned unused. **Ruling each class of disagreement is step 4 and has not started.** ⚠ Two gaps filed rather than papered over: `DEF-1900` — no control on AST-05/AST-01/02 and **no SIZE column on the meters import**, so a utility loading 1,847 meters still gets the every-size ladder and only an API call can set a size; and `DEF-1901` — `route_meter_picker` publishes neither `service` nor `read_method` either.** Adapter + shadow shipped (`06-backend/apps/billing/resolution_shadow.py`; 13 tests; 3 guards proved RED first); **nothing on any bill changed, by design.** ⛔ **STEP 3 MEASURED THAT THE CHAIN CANNOT BE RUN ON A SINGLE REAL ACCOUNT OF ANY TENANT** (`DEF-1811`, critical): `accounts 1 · attempted 0 · disagreed 0 · blocked {connection_size_unresolved: 1}` — R3 needs a connection size and **the product stores one on no table** (`DEF-514`). **So `DEF-438` is not "no production caller", it is "no production caller is CONSTRUCTIBLE", and the blocker is a METERING COLUMN, not billing work.** Two more of that shape: no multiplier crosses billing's read seam (`DEF-1812`), no billable asset count crosses at all (`DEF-1813`). And `DEF-1810` — R3's size refusal is unreachable through any correct adapter (worked: an unconfigured `3-inch` resolves to the same `$8.00` as `5/8`), **which invalidates this step's recorded acceptance test as written**. ⇒ **NEXT, IN METERING: source the size, then publish the multiplier, then the count. Step 4 has nothing to rule until one account can be attempted** — which is also why nothing went to the PO. `DEF-652` was found ALREADY RULED and was NOT re-asked (law 13). Full reasoning: decision log 2026-08-27, *"R1–R7 STEP 3, DELIVERED"*  ⚠ **STEP 5’S MECHANISM LANDED 2026-08-28; STEP 5 ITSELF HAS NOT STARTED** (decision log same day, *"THE PER-STEP SWITCH"*). There was no seam a SINGLE rule could cross — the only move available was swapping all seven at once, which this very method forbids by name — and `06-backend/apps/billing/resolution_switch.py` is that seam (`BR-BIL-870`–`BR-BIL-874`). **Three of eight steps have a fork**: R3+R4 → the base charge (they switch together, because `resolve()` produces one base from both) and R5 → the jurisdiction factor; naming any of the other five REFUSES rather than being accepted and ignored. **Nothing is switched on and no bill moved** — the choice is carried by a deployment setting that is empty everywhere, `apply()` returns the object it was handed, golden-verify **33 PASS / 0 FAIL** and `run_gates` unchanged at its **41 PASS / 13 FAIL** baseline. **It was flipped BOTH WAYS on one real account**, because a switch nobody has flipped is a comment claiming a guarantee: water base **$8.00 → $12.50 → $8.00**. That middle figure is the live `R3/R4` disagreement (`BR-RAT-088`’s charge code against `plan_services.base_charge`, which no tenant has migrated — `DEF-455`) and it is **$4.50 a month on every water connection**. ⇒ **NEXT: run the shadow across a REAL RUN rather than one account, then step 4 — rule each class. R3+R4 is the nearest candidate and cannot be switched until that $4.50 is ruled.** ⚠ **STEP 3'S SCREEN HALF LANDED 2026-08-28 AND THE NEXT LINE OF THIS CELL IS NOW DONE** (decision log same day, *"R1–R7 STEP 3, THE SCREEN HALF"*). The shadow runs **across a whole bill run, not one account**, and its report is on S31.2 — `apps/billing/shadow_report.py` + `GET /billing/runs/{id}/pricing-shadow` + the **Compare the new pricing** panel. It prices nothing and `runs.py` does not import it, so a fault in it cannot reach a bill. **What an operator reads, verbatim:** *"We worked out 1 of 1 customers both ways. 1 came out differently. 0 could not be worked out at all."* — the attempted count is in the SAME translated sentence as the disagreement count in all eleven catalogues, because *"0 disagreed"* is also what a chain that never ran looks like. Each class row carries **how many customers it touches** and both answers side by side, and the panel chooses neither and computes no difference. **The class the seeded run surfaces is `R1 · NoPlanInForce` on 1 customer** — the ruled path will not price ACC-1042 at all while today's billing bills it on *Residential Standard (v1) — electric base 18.50 on version 7*. ⚠ **WHICH CLASS YOU SEE DEPENDS ON THE ACCOUNT, because the chain refuses at the FIRST step that fails** — the harness fixture above surfaces `R4` and the run fixture surfaces `R1`, and both are real. **STEP 4 IS NOW THE ONLY THING IN THE WAY and it is the PO's**: the list is on the screen and in `12-governance/09-human-review-ledger.md`. ⚠ **STALE THE SAME DAY, STAMPED RATHER THAN REWRITTEN (2026-08-28): THIS CLASS HAS BEEN RULED AND BUILT.** `DEF-494` closed at `ddb0b61` — *a rate plan cannot be published without a start date* (`BR-RAT-890`), on the PO's ruling of the same day — which is exactly the disagreement this row was written to put up for decision. **So it is no longer waiting on anybody.** The measurement above stands as a measurement and the ask does not. ⚠ **AND IT IS THE SECOND TIME IN ONE ENTRY THAT A SENTENCE OF THIS LANE'S DECAYED BEFORE IT WAS READ** — the first was a claim about a door that already existed (§9(b)). **The shape is the lesson: a statement about what the product cannot do, or has not decided, is precisely what another lane is working to change, so it must be re-measured at push time and not at dispatch time.** It costs one grep. Two things filed rather than absorbed: `DEF-2401` (the adapter asks metering three questions per account, so the panel is O(accounts) queries — on no bill path, so it cannot slow a run) and `DEF-2400` (a guard of ours that passed on its own mutation, caught before merge). `DEF-2550`'s stale trailer is amended in the same commit. |
| **2** | **Normalise the register, and wire `G46` in the SAME commit** | 270 rows in a second vocabulary. Every count taken from `severity` has been wrong — *"40 high open"* was really **90** on the day it was
said, and **89** after this commit's own two row changes. **Both figures are the wide reading of "open" in
the table above; neither is the narrow one.** That a one-line correction already needs two numbers and a
definition is the whole argument for step 5. Step 4 triages from these numbers, so this comes first or the prioritisation is built on noise. **G46 exists and is proved RED; it is deliberately unregistered until the rows are clean, so the suite goes green to green** | ✅ **DONE 2026-08-27** — 270 rows collapsed, `DEF-358`'s shifted field repaired by hand, G46 registered, all in one commit. ⚠ **AND IT WAS MORE URGENT THAN THIS ROW SAID:** G46 shipped unregistered, and `_assert_registry_sane` refuses to run the suite at all when a gate module has no row — so **the whole gate suite had been refusing to start for every lane on the branch** since `f5c9fb1` (`DEF-1783`, critical). The reason was written in the gate's docstring, where no code reads it |
| **3** | **Three boundary gates** — frontend↔seed · import↔ledger · template↔series | **Every existing gate compares a frontend artefact to another frontend artefact, or a document to a document.** The three worst escapes of 2026-08-27 each crossed a boundary nothing watches: signup offering **6 of 10** services with a green tick; migrated deposits writing the register and posting **nothing** ($750 vs $0.00); meters numbered from the file. `G44` and `G45` are the two that broke the pattern and both caught real defects the day they landed. **Highest leverage on this list — the difference between finding the next batch and shipping it** | ✅ **DONE 2026-08-27** — `G47` service-catalog-parity (frontend↔seed) · `G48` import-money-posts (import↔ledger) · `G49` identifier-series-contract (template↔series). Each meets the dispatch contract from `DEF-1785`: `run()` **and** a `__main__` block (G42), registered in `run_gates.GATES` in the SAME commit that adds the file, a `selftest()` proving every clause bites that RUNS INSIDE `run()`, and a verbatim RED proof. Suite **32 PASS/15 FAIL → 36 PASS/14 FAIL**; no gate broken. Found `DEF-1840` (G49 clause (d) — five served strings name a Settings tab that does not exist, and TWO TESTS PIN THE WRONG WORDING, so the suite was green on the bug) and `DEF-1841` (the R1–R7 chain is rating math, is marked HUMAN-OWNED, and no glob in `human_owned.txt` matches it — G7 has never looked at it; the third occurrence of an escape that file records twice in its own words). ⚠ **THE FOURTH GATE WAS NOT BUILT, AND THAT IS A RECORDED JUDGMENT RATHER THAN AN OMISSION** — it is genuinely uncovered by G13/G40/G20, but its only workable scope (the 🔒 set) has the hole `DEF-1841` names, so building it now would ship false assurance. Decision log 2026-08-27, *"THE THREE BOUNDARY GATES, AND WHY THERE IS NO FOURTH"* §4, carries the measurement so the next lane starts from data |
| **3b** | **THE GATES THAT ARE ALREADY RED — 14 of them, and NONE of the five steps above was about them** | **This row exists because the suite could not start.** `DEF-1785` meant `run_gates.py` was a hard refusal for every lane since `f5c9fb1`; the first run after it was fixed printed **32 PASS / 15 FAIL**, and no plan had a line for any of it. `G12` was **one command** (a stale derived index) and is already green — 14 now. **TRIAGED BY WHAT A CUSTOMER SEES, and the triage MOVED THREE OF THEM, so read it rather than the headlines.** ⚠ `G27` says *"19 components render raw translation keys"* and **that sentence is wrong** — `ConnectionDetailPage` has 123 `t()` calls and 122 `defaultValue` clauses, so its 107 keys render correct ENGLISH. It is a translation-COVERAGE gap, not a raw key on screen, and it is filed as `DEF-1788`. **The genuinely user-visible set is small and was buried underneath it:** `G28` — 76 violations against a baseline of **0** — puts internal register ids in front of a customer (`de.json :: metering.import.mappingBlocked` ends *"(DEF-5…)"*); `G32`'s four close-out refusals resolve to **silence**; `G18` names the **one** key that truly renders raw; `G15`'s ten parity failures show English to a German reader. **The other nine are traceability and hygiene** — `G1`/`G3`/`G7`/`G11` migration trailers and review-ledger rows, `G10` TC-named tests, `G14` prototype headings (228 against a 195 baseline), `G26` required rows, `G33` refusal length. | ◑ **THE FOUR CUSTOMER-VISIBLE GATES ARE DONE, AND ONLY TWO OF THEM WERE WHAT THE HEADLINE SAID** (2026-08-27, step-3b lane; decision log same day). **`G32` GREEN** — the close-out's refusals speak in eleven languages, six of them, not the four the gate can see (`DEF-1650` closed). **`G28` PART 1: 76 → 0** against its zero baseline, nothing baselined, provenance moved to the code comments — and the gate had undercounted itself by one (`DEF-1861`: `ko-KR` held the same id and a `\b` cannot see it past a Korean letter), so 77 were fixed. **G28 still FAILS on Part 3 alone** — 555 raise sites against 498, count-only so nobody can find their own lines, 240 of them in `rating`/`billing`, and not rendered to anyone since `params.detail` was suppressed (`DEF-1860`). **`G18`'s ONE "renders raw to a user" finding is a FALSE POSITIVE** (`DEF-1862`) — a dot-plural stem resolved by `pluralKey()`, both halves in all eleven catalogues, with two tests proving it; 46 STALE register lines were deleted instead (3 failure clauses → 2) and the 181 dead keys were left alone on purpose. **`G15`'s ten failures are TWO defects in one shape** (`DEF-1863`): five locales at ~1,128 untranslated values (the translation order, `OQ-740`/`741`) and five whose 60 residuals contain **no English word at all** — de's five are `+{{count}}` and four like it, so *"a German reader sees English"* was not true of one of them. Shipped as **2.79.4**. ✅ **VERIFIED AT THE TIP BY THE MERGE LANE: 38 PASS / 13 FAIL** — the suite began the day *refusing to start* and read 15 FAIL on its first complete run; `G12` and `G32` are the two that closed, and **all five gates added today (`G46`–`G50`) PASS.** |
| **4** | **The open highs, in MODULE BLOCKS** — re-measured 2026-08-27: **customers 17 · rating 17 · billing 11 · platform 7 · metering 7 · notifications 6 · governance 5** (70 of the 90 in seven blocks; the figures this row shipped with — *rating 20 · customers 19 · billing 12 · platform 8 · metering 8* — were taken before the severity collapse and are superseded) | By module, not by id: a cluster costs a fraction of its members fixed separately. ⚠ **`DEF-135` is pulled UP to sit beside the criticals** — *"thirteen ruled rules have no door"* is `DEF-438`'s exact shape, thirteen times over. ⚠⚠ **AND THE BIGGEST CLUSTER IS NOT A MODULE AT ALL — IT CUTS ACROSS FIVE OF THEM (`DEF-1793`).** Twelve of the 90 highs are REACHABILITY defects (`built-not-wired` 7 · `unwired` 3 · `unwired-contract` 2), and **all four gates in that family pass**: `G13`/`G40`/`G45` scan `07-frontend` only, and `G27 engine-surface` is whole-module and fails **only at zero routes** by its own specification. So a module serving 32 routes hides an unrouted seventh service perfectly — `DEF-478`, *"six more discount write services reach no route"*, sits in `rating`, which `G27` scores healthy. **Fix the cluster with a fifth sibling gate, not twelve tickets** | ⚠ **FIRST BLOCK DONE — AND IT LANDED ON THE REGISTER, NOT THE PRODUCT (`DEF-1930`).** Of the nine, **SEVEN WERE ALREADY FIXED AT THE TIP AND STILL READ `open` WITH AN EMPTY `fixed_commit`** — `service_request_service.py:12` says so in its own words, *"DEF-634 ✅ · DEF-635 ✅ · DEF-637 ✅ · DEF-638 12.a ✅ — all closed"*, over rows that all said open, with **83 green tests** behind them. **A whole triage lane was aimed at shipped work.** Two were real: `DEF-628` (whose own prescribed fix — *"key off `non_billable`"* — would have shipped a WORSE defect, because `BR-CUS-107` put `Disconnected` in that class the next day and its worked row `A-11488` is **cut owing $612.75**; now `BR-CUS-510`, four conditions) and `DEF-638 12.c`. Four more were **not defects**. **`G51` is the prevention** — code claiming `DEF-### ✅` may not point at a row that is not closed; G50's mirror, hard zero, registered in the same commit. **⚠ THE CAVEAT THIS PUTS ON EVERY NUMBER IN THIS FILE, INCLUDING MINE:** the open counts are as good as the register's closures, and the one cluster anybody re-triaged came back **78% stale**. Open highs read **84** now, not 90. **That is one sample and it is not a rate** — three rows repo-wide are directly self-contradictory (`open` with a `fixed_commit`), and 55 of the 84 have their id mentioned in source, **which is NOT evidence of a fix**: `tracks:` markers name UNFIXED work and tests are named for the defects they prove. Measure before believing either direction |
| **5** | **Derive CR status lines instead of typing them** | Not a defect, and the most expensive failure of 2026-08-27: **four separate findings were stale SENTENCES** (`DEF-978`, its owed-list twin, `DEF-1790`, `DEF-1712`). Twice we came within one grep of spending a lane on finished work. `10-scripts/cr045_toolbar_sweep.py` proves the shape — it reports *wired · custom · declared · inert · bare* rather than a boolean, and immediately exposed four screens whose filter control renders and ignores every click, which a hand count had scored as done | ◑ **TWO HALVES LANDED 2026-08-27.** (a) `G50` refuses a sentence claiming a defect was FILED whose row does not exist — hard zero, no legacy, `DEF-1792` closed. ⚠ **The obvious gate, *every cited id resolves*, was written, measured and THROWN AWAY**: 24 of its 24 hits were false positives of the check (reservation ranges, an unpadded id, a truncated German quote, abandoned ids cited *as* abandoned) — shipping it would have made a fifth gate that misdescribes its own output. (b) `defect_report.py` now prints **both** readings of *open* with their severity split and the difference between them, because three different open counts were in circulation at once (`DEF-1786`). **STILL OWED: nothing checks a figure TYPED in prose against the register** — that is the half a gate cannot do without a marker convention, and it is the next work here |

## THE FOUR TESTS THAT PRODUCED THIS ORDER

Recorded in full in the decision log; stated here so the order can be argued with rather than merely followed.

1. **Can it take or lose money wrongly?** Money is irreversible by hard rule 4 — a posted entry is corrected by
   a new entry, never edited. A money defect's cleanup **grows every day it is live**.
2. **Does it fail silently?** A **multiplier on test 1, not a separate concern.** A loud defect is reported in a
   day; a silent one is found at a bill run, an audit, or by a customer.
3. **Does it stop a utility from STARTING?** Onboarding and migration gate everything downstream.
4. **How many other rows does it EXPLAIN?** Cluster roots before cluster members.

**Severity is an INPUT to these, never the ranking** — the column holds nine values across two vocabularies,
which is what step 2 exists to fix.

## ⏸ NAMED, NOT SCHEDULED — work the PO has deferred, with the trigger that reopens it

**This section exists because the repo had nowhere to put a thing that is genuinely coming and
genuinely not next.** THE SEQUENCE above is ordered work; the decision log is append-only and
cannot hold a status that will move; `01-open-questions.md` is for questions **we** need
answered, and these are already answered. So a deferred item was landing either in a sequence
it would distort or in a log where it would be read once and lost.

**The rule for this table is the trigger, not the date.** An item here is not *"later"* in the
vague sense — it has a named event that reopens it, and **nobody should re-raise one because a
release shipped or a quarter turned.** An item with no trigger does not belong here; it belongs
in THE SEQUENCE or nowhere.

| Item | What it is | Deferred by | Trigger that reopens it | State |
|---|---|---|---|---|
| **Pricing model + the Bynry admin side** | The public Pricing page's three bands top out at **3,000 accounts (T7 only)** while the ICP now reaches **40,000 (T5)** — `public.plan.starter.f1` *"Up to 300 active connections"*, `growth` *"Up to 1,000"*, `scale` *"Up to 3,000"*, in **all eleven catalogues**, at $1,000/$5,000/$8,000 a month. The wider piece behind it is the pricing model itself and the Bynry-admin surface that would operate it | **PO ruling 2026-09-06**, verbatim: *"Keep it as it is for timebeing - once product stablise then we will work on ricing and Bynry admin side of thing thats when we take care of pricing model"* | **The pricing-model work starting.** NOT a date, NOT a version, and NOT "when someone notices the mismatch" | ⏸ **DEFERRED, DELIBERATELY.** ⚠ **Those six numbers are not a bug and must not be "fixed"** — they are commercial figures and `NFR-5` already rules them *"commercial only"*. Recorded as `DEF-TEN-4222`, status `wontfix`, which **overstates it**: `G46` enforces a closed status vocabulary with no `deferred` value, and of the nine allowed that is the only one meaning *a deliberate decision not to act*. **If a `deferred` status is ever added, this row moves first.** Full reasoning: `02-decision-log.md` 2026-09-06, *"THE PRICING PAGE STAYS AT 3,000"* |

## HOW TO USE THIS FILE

* **Update the State column in place.** That is the whole reason this file exists.
* **Do not restate the reasoning here when it changes** — put it in the decision log and leave a pointer.
* **If the order changes, say who changed it and why**, in the log. An execution order nobody can trace back to
  a judgment is the stale-sentence failure this file's own step 5 is about.

## ⚠ THE GO-LIVE PATH — what test 3 ranks AGAINST (added 2026-08-28, PO asked for it)

The four tests in `02-decision-log.md` (2026-08-27, *"HOW TO PRIORITISE THIS REGISTER"*)
are the ruling and are unchanged. **Test 3 — *"does it stop a utility from STARTING?"* —
had nothing concrete to point at**, so each session re-derived what "starting" means. This
is that list, and it is the only thing added here.

**A real utility walks these in order. Fix the EARLIEST break first**, because a later break
cannot even be observed until the earlier one clears — the shadow report read
`0 disagreed` for weeks and that was indistinguishable from perfect agreement, purely
because a step further up had not landed.

| # | Step | It is broken if… |
|---|---|---|
| 1 | **Sign up and provision** | a new utility cannot get a working tenant with its lists, chart of accounts and numbering |
| 2 | **Configure services and prices** | the utility cannot express what it charges — including *declaring* what kind of service it is |
| 3 | **Load premises and units** | the address book cannot be imported |
| 4 | **Load meters** | equipment cannot be imported, or carries no fact the price depends on |
| 5 | **Load accounts, opening balances and deposits** | customers cannot be migrated, or arrive without what they owe |
| 6 | **Enter reads** | consumption cannot be captured or estimated |
| 7 | **Run a bill** | the run will not produce a draft |
| 8 | **ISSUE it** | the draft cannot become an immutable financial record |
| 9 | **Deliver it** | the customer never receives it |
| 10 | **Take payment** | money cannot be recorded against the bill |
| 11 | **Books tie out** | the register and the ledger disagree |
| 12 | **Exceptions** | disconnect, transfer, refund, move-in/out cannot be worked |

**Steps 7 and 8 are deliberately separate.** A bill that drafts and previews and then
refuses at issue looks healthy on every screen a lane checks — `DEF-536` is exactly that
and it stops every discounted bill.

### THREE TIE-BREAKERS, when the four tests leave two items level

1. **A rule with nothing that can SET it outranks a rule that is merely wrong.** It looks
   finished and is not — hard-won law 2. Five of these were closed on 2026-08-28 alone
   (the meter's connection size, per-size prices, the outside-city surcharge, deposits,
   the unmetered cart count) and each had a reader, a migration and no writer.
2. **Prefer the item that unblocks the most others.** `DEF-1813` was one row and it was the
   last of four missing facts blocking the whole engine cutover.
3. **Fix the unrecoverable direction first.** Under-charging is corrected next cycle;
   over-charging is a credit note per customer, because hard rule 4 makes an issued bill
   immutable. When two fixes compete, take the one that cannot be taken back.

### ⚠ VERIFY THE ROW BEFORE YOU WORK IT

The register runs about **20% stale** — measured, not estimated: a random sample of 15 open
high-severity rows found 3 already fixed (Wilson 95% CI 7–45%). **Re-read the code, not the
row.** A day was spent aiming a team at work that was already finished.
