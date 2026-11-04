# CR-038 + CR-039 — everything waiting on you, in one sitting

**Date assembled:** 2026-08-26 · **For:** Product Owner · **Assembled by:** the
CR-038/CR-039 merge lane · **Version at assembly:** 2.52.0

---

## How to read this, and why it is written this way

Your standing instruction of 2026-08-11, verbatim:

> *"you give me all these codes; im human dont understand"*

So **nothing below is a code to go and look up**. Every item is the question in
plain English with the concrete number it turns on, and the options with what
each one costs. The codes are in the right-hand margin only so the answer can be
filed; you never need to read them.

**A signature covers only what was shown.** If an item here is unclear, saying
"okay" to it records nothing — ask instead, and it comes back expanded. That is
not a formality: three items in an earlier batch were answered *"okay"* against
questions nobody had expanded, and none of the three could be written down.

**Ten items. One is money that is wrong today.** It is first for that reason.

---

## 1 · A demand reading's unit — and a demand charge is mis-billed right now

**The question:** when a meter records a customer's *peak rate of draw*, what
unit is that number in?

**Why it is not obvious.** A peak rate of draw is measured in **kW**. A quantity
of energy is measured in **kWh**. They are different things — kW is how hard you
were pulling at your worst moment, kWh is how much you used all month — and the
product currently says both. The reading is stored in the meter's own unit, so a
peak taken on an electric meter is filed as **kWh**. But the price is
per-kW, the rating contract says kW, and the screen itself reads *"Demand (peak
kW)"*.

**What it costs, measured:** a **412 kW** peak billed as though it were 14 kWh
charges the customer **$154.00**. The correct charge is **$4,532.00**. That is a
real commercial account being undercharged by $4,378.00 in one month.

| Option | What happens | Cost |
|---|---|---|
| **(a) A demand reading carries kW** *(recommended)* | the store records the unit per channel rather than per meter, so one meter can hold kWh on one register and kW on another | one schema change; it is what every other statement in the product already assumes |
| **(b) It carries the meter's unit** | every consumer converts on the way out | the same conversion written in several places, and each is a chance to get it wrong |

⚠ **Whichever you rule, the QUANTITY is wrong independently of its label.**
Fixing the unit alone would print a correct unit on a wrong number. Both halves
are fixed together or neither is.

*(Files as OQ-391 and DEF-797.)*

---

## 2 · Three buttons the prototype draws that we did not build

The bill run's read-analysis tabs let a clerk deal with a suspicious reading.
The prototype draws a `Fix` control on every row; we built them all **except
three**, because building each one would have invented a rule nobody made.

**(a) "Override" on an estimated reading** — a clerk types a quantity that
replaces a measured one. No rule permits a typed number to stand in for a
measured one at bill time. The lawful route already exists: correct the reading
through metering, which records who corrected it and why.

**(b) "Cap at 2×" on a high reading** — bills at most twice normal. This does
two forbidden things at once: it invents a threshold (no threshold is ever
hardcoded), and it edits a measured quantity. Worked case: a meter reading
**26.24 kgal** against an **8.40 kgal** average would bill **16.80 kgal**, and
the **9.44 kgal** difference is either water the utility never charges for, or a
leak nobody investigates.

**(c) "Change to ×1" on a meter factor** — writes the multiplier on the METER
from inside a bill run, and silently reprices every future reading on it.

| Option | What happens |
|---|---|
| **(1) All three stay out** *(recommended)* | the prototype is stale on this point; the lawful routes — correct the reading, investigate the high one, edit the meter — are all reachable today |
| **(2) Rule what each one needs** | tell us the rule, and they get built |

*(Files as OQ-390.)*

---

## 3 · Three old words for "how was this read" that match none of your five

You ruled the vocabulary: **Manual · Walk-by · AMI · AMR · Mobile.**

Readings already stored carry six older words. Three map cleanly and are done.
**Three do not, and we refused to guess:** `drive_by`, `self_read` and
`field_visit`. A drive-by is not necessarily AMR. A self-read is not necessarily
Manual. A field visit is not necessarily Mobile. So every reading collected under
those three words currently shows **no method at all**, and the screens say so
rather than showing a value nobody recorded.

⚠ **The repo already contradicts itself on one of them.** A demo fixture comment
calls Mobile *"the seeded read-method code for a drive-by round"* — asserting
drive-by ≈ Mobile by comment rather than by your ruling. That comment is not a
decision and is not being treated as one.

| Option | What happens |
|---|---|
| **(a) Rule each of the three onto one of the five** *(recommended)* | the mapping closes and history can later be backfilled under a flagged migration |
| **(b) Leave them unmapped** | those readings say *not stated* forever, honestly |

*(Files as OQ-392.)*

---

## 4 · Should "how it was read" be part of what makes two uploads the same file?

The product blocks the same file being uploaded twice. What counts as "the same
file" is the file itself plus the tags on it — the month, the cycle, the route.
**The read method is one of those tags**, so on a plain reading of the rule it
belongs in that check. We deliberately did not add it, because it is not a
lane's call.

**Why.** Adding a field changes what an identical re-upload computes. **Every
batch posted before today would stop matching itself**, and the double-post
block would quietly stop protecting the history you already have.

**And the cost of leaving it out, stated plainly:** two uploads of the *same
file* tagged with *different methods* count as one, so the second is refused as
a duplicate. That is arguably right — they are the same readings — and arguably
wrong, because the second upload asserts a different fact about how they were
collected.

| Option | What happens |
|---|---|
| **(a) Leave it out** *(recommended until someone needs it)* | a re-upload under a corrected method is not possible |
| **(b) Add it** | it becomes possible, and historical batches no longer protect themselves |

*(Files as OQ-393. 🔒 idempotency is a sensitive path — this is why it is asked.)*

---

## 5 · At a move-out, does the last known reading appear IN the box, or under it?

A clerk opens the move-out wizard for a unit. The meter's last committed reading
is **42,864 kWh**, taken eight days ago. The clerk has to enter the final read.

| Option | What the clerk sees | Cost |
|---|---|---|
| **(a) The box opens with 42,864 in it** | ready to accept or overwrite | ⚠ **a reading nobody took becomes the reading of record by inaction.** A clerk in a hurry presses Next, and an eight-day-old number closes the account, bills the final invoice, and is what the next occupant is measured from. Those eight days bill as **zero** |
| **(b) Empty box, "Last read 42,864 kWh on 2026-08-18" underneath** *(what we built)* | the clerk types it every time | slower, including when the meter genuinely has not moved |

**We built (b) and are telling you we chose**, because the written rule says
"prefill" and we read it as ambiguous. Reversing it is one line and a test — no
migration, no data, no money rule.

*(Files as OQ-394.)*

---

## 6 · One file needs your permission to be watched

There is a list of files that only a human may sign off on — the money math, the
tenant isolation, the ledger. **Changing that list is itself something only you
can do**, deliberately: a lane may not add its own file to the list of files
being watched, or the watching means nothing.

`apps/billing/read_analysis.py` prices the **true-up** figure a clerk acts on,
and it matches nothing on that list, so the gate reports "all clear" over it.
**This is the third time this exact thing has happened to a money path** — the
two before it are recorded on the list itself.

**Ask: add it.** *(One word. Files as DEF-793.)*

---

## 7 · The true-up figure itself, for ratification

When an account was billed on estimates and a real reading finally arrives, the
product shows what the difference is worth so a clerk can decide.

**Worked case:** an account billed on two estimated cycles at **1,236 kWh**,
whose actual reading lands at **1,410 kWh**, is trued up by **+174 kWh**. The
money shown is what the pricing engine charges for that 174 on **that account's
own tariff** — never a rate this file holds. It writes nothing. When pricing
refuses to answer, it shows the **quantity** with the refusal named, rather than
a number nobody computed.

**Ask: is that the right thing to show a clerk?**

---

## 8 · When a setup step is SKIPPED rather than failed, should it go in the audit trail?

You ruled that a failed setup job writes to the tenant's audit trail with an
error code. Built, and it works.

**One case is not obviously covered and we chose:** a step that is skipped
because the feature it needs *does not exist yet in the product* writes **no**
audit row. Our reasoning: that is a gap identical on every tenant, and a row per
tenant per run would bury the failures that are actually about that tenant. The
existing summary row still names every short module.

**Ask: is that right, or should a skip be recorded too?** *(Reversing it is
small. Files as BR-TEN-083 clause 4.)*

---

## 9 · Two checks this repo specified and never built

Both are ours to build; both change how merges are blocked, which is why they
are shown rather than done.

**(a) Nothing runs the migration-safety check.** It appears in every lane's
report as a line somebody types, and no script runs it. It had been **failing
for days** under a green claim. We fixed the failure; nothing stops the next one.

**(b) A version can still be cut with no changelog entry.** The change process
says a gate must refuse exactly that. **2.52.0 was cut with no entry** — the very
next version after the rule was written. We wrote the missing entry by hand.

**Ask: build both?** *(Recommended. Files as OQ-395 and DEF-806.)*

---

## 10 · One small permission — a translation the gate calls untranslated

The monthly-usage chart shows a tooltip that is nothing but the month, the
number and the unit — `March: 1,410 kWh`. There is no word in it to translate,
so all eleven languages hold the same string, and the translation check reads
that as "never translated".

The fix is one line on an exemption list. **That list is a ratified gate, and
its own rules say adding a line goes to you** rather than being slipped in.

**Ask: allow it.** *(One word.)*

---

## Not in this batch, and why

**The five CR-039 questions from the tenant-provisioning walkthrough** — whether
all ten services appear at signup, what an "owner" is, what a move-in and
move-out are as records, the meter size-class bands for all ten services, and
the term/add-on pricing — are **not expanded here.** They were put to you on a
web page rather than in the repo, and expanding them properly needs that page's
content brought across first. Listing them as five bare titles would be exactly
the "codes to look up" form your instruction forbids, so they wait for a batch
that does them justice rather than riding along badly done here.

---

## What is NOT waiting on you

So the size of the ask is clear: **CR-038 has nine of eleven waves merged and
green**, and CR-039's seeding-visibility wave is merged. Four lanes are building
the rest. Nothing in this file blocks that work — every item here is either a
choice between two lawful behaviours, or a permission only you can give.

The one exception is **item 1**, which is a wrong charge in the product today.

---

# PART TWO — five more, added 2026-08-26 21:45 as the last four waves landed

The ten above were assembled while four waves were still building. Those waves
are now merged, and they raised five more questions on the way. **Same rules:
plain English, the number it turns on, no codes to look up.** They are second
because none of them is money that is wrong today; item 1 above still is.

---

## 11 · Two of your three write modes currently do the same thing

You asked for three modes at step 1: *Insert new only · Insert & update ·
Replace*. All three are built. **The second and third behave identically to
readings**, and that is not a bug in the build — it is what the written
semantics say when you actually try to implement them. *"Supersedes a committed
duplicate"* and *"supersedes everything the file carries"* are the same set of
rows, because a file only ever carries the rows it carries.

**The real question is what `Replace` should do to a reading that is ON FILE and
NOT IN THE FILE** — the whole point of calling it "replace" rather than
"update". Two of the possible answers are marked forbidden rather than offered:
**deleting** those readings, and **superseding them by nothing**. Both destroy
measured history, and issued bills were priced from it.

**Nothing is stuck.** The mode is recorded on every batch, so whichever way you
rule applies to batches already uploaded, with no data migration.

*(OQ-418.)*

---

## 12 · Should the monthly usage figure be stored per METER, or computed?

You asked for twelve months of consumption *"on account and meters"*. Both are
built. The account reads a stored monthly row; **the meter computes from the
readings**, because the stored row has no per-meter grain — it is kept per
account, per service, per month.

The rules are literally the same functions, a test holds the two surfaces
against each other, and both the data and the screen say *computed from reads*
rather than implying a stored figure. So nothing is wrong today.

**Why it is asked rather than decided:** adding the meter dimension later is a
migration. Removing it later is **dropping a column that has data in it**. That
asymmetry is the whole reason a lane would not choose for you.

*(OQ-421.)*

---

## 13 · A clerk at the counter, and the meter is on no cycle

A customer is standing there. The clerk has meter M-5002 and a reading of
**1,300 kWh** taken today. The meter belongs to no route, or to a route on no
cycle — a new connection not yet on a walk, or a meter whose route membership
moved.

Today the reading is **accepted**, with the absence shown on screen. The
recommendation is to **warn** instead — accept it, and say plainly that it
belongs to no cycle so somebody fixes the route. What it must not do is refuse:
the reading is real and the customer is in front of them.

*(OQ-422.)*

---

## 14 · The onboarding "opening reads" step needs a NAME, not a build

This one is smaller than it sounds and worth thirty seconds. The last step of
loading a new utility's data is its opening meter readings. **The rail for it
already exists** — opening reads are meter readings in a file, and a clerk can
upload them today and they post correctly.

What is missing is a **word**. The five events a reading can be attached to are
named — move-in, move-out, transfer, disconnect, new connect — and an opening
read at cutover is none of those. The lane refused to quietly add a sixth to a
list you had enumerated hours earlier.

**Ask: is a cutover opening read a sixth kind of event read, or is it just an
ordinary upload that happens to be first?** *(OQ-419.)*

---

## 15 · The co-sign records who signed and does not yet BLOCK

A second person can now co-sign a read batch — the field for it had been on
screen and unwritable since it shipped. What is **not** built is the part where
a utility turns co-signing ON and the post is then refused until somebody signs.

The data says so out loud (`cosign blocks post: false`) rather than letting a
screen imply a protection that is not there. Its home is a settings screen a
different wave owns.

**Ask: build the blocking half now, or leave the record-only version?**
*(DEF-815.)*

---

## ⚠ There is no item 16

It was a pointer back to item 8, and a duplicate in a list of decisions is
worse than a gap — it makes the same question look like two. **Nineteen items,
numbered 1–15 and 17–20.** The number is left absent rather than the list
renumbered, so a reference to "item 18" written earlier still finds item 18.

---

## 17 · Three sub-area names, and two districts deliberately left flat

You asked why a new tenant had no sub-areas: *"Why you dont have sub areas below
- Areas metering 4 North district · Downtown · East district · Industrial
corridor"*. They exist now. **What nobody has shown you is the result.**

A new tenant's Areas list goes from **4 to 7**:

| District | Sub-areas seeded |
|---|---|
| North district | **NE**, **NW** |
| East district | **SE** |
| Downtown | *none* |
| Industrial corridor | *none* |

⚠ **The two empty ones are a decision, not an oversight.** Without a district
that has no children, the *"no sub-areas"* help text and a plain district path
cannot be seen on a seeded tenant — so a demo would never show what a flat
district looks like.

**Ask: keep these three, name them yourself, or seed none and let each utility
fill the second level?** The recommendation is to keep them — they are compass
subdivisions of your own district names and invent nothing. But a seeded
reference list is what every demo and every new tenant opens on, so these names
are the product's first answer to *what does a district look like here*.

*(OQ-432. The lane that built this flagged it rather than passing it off as
ruled, and had no question id left in its reserved range to raise it with.)*

---

---

## 18 · What number should a transfer carry? And should a disconnect carry one at all?

A transfer and a disconnect case can now be quoted down a phone — **almost**.
Both records take a reference number, allocated the moment the record is
created. Neither has a **format**, and that is deliberate.

**The rule this product holds itself to:** a seeded number format is taken from
what the prototype actually draws, never invented. A connection is
`CON-26-0110` because those screens draw exactly that.

**The transfer and disconnect screens draw no reference column at all.** Their
rows are identified by account number on both sides — `A-10650 → A-11940`,
`A-11507`. So the lane refused both prefixes rather than pick two that nobody
could look up later.

**⚠ And they are not the same question, which is the part worth your time.**

| | |
|---|---|
| **A transfer** | needs a number of its own — it is one job spanning two accounts, and neither account number names it. Recommendation: **`TRF-26-0001`**. |
| **A disconnect** | may need nothing. **The prototype draws a disconnection as a WORK ORDER** — `WO-4833` — so a disconnect case may not be its own document at all. This one carries **no recommendation**, because the honest answer might be "don't give it a series". |

Until you rule, a new record shows **the reason it has no number** rather than a
dash or an invented one. **Closing either is one catalogue row and no schema
change.**

*(OQ-426 and OQ-427.)*

---

---

## 19 · Six months marked as the wrong side of the city line — does the customer get money back?

A premises can now be marked **inside** or **outside** the city, which decides
whether its bill carries the surcharge. Correcting a wrong mark applies
**forward only** and touches no bill already issued — issued money does not
change by itself, and that is a rule you have already signed.

**What is not settled is whether it OWES anything.** If a building was marked
wrong for six months, that is roughly **$350** the customer was over- or
under-charged. The code does forward-only and **says so out loud** rather than
letting the absence imply it.

**Ask: on a corrected jurisdiction, does the product raise an adjustment for the
period already billed, or leave it to a person to decide case by case?**

*(OQ-423.)*

---

## 20 · Two rules you have already signed meet for the first time, and nobody has said what they mean together

This one is small in words and worth reading slowly.

- **Sewer is exempt from the city surcharge**, and its base is $0.00 — so "flat
  everywhere" reaches nothing.
- **The sewer charge is 40% of the water charge** — and the surcharge has
  already moved that water charge.

So on an outside-city address, the sewer charge goes **$43.60 → $65.40**,
because the water figure it is a percentage OF went up. Sewer is exempt and its
bill still rose.

**Neither rule is wrong.** They were signed at different times for different
reasons and have never been applied to the same bill until now.

**Ask: is that the intended outcome — sewer follows the water charge including
its surcharge — or should sewer be 40% of the pre-surcharge water figure?** The
lane deliberately did **not** stub this: refusing to bill in order to ask a
question would be worse than billing what two signed rules compose to and
flagging it.

*(OQ-424.)*

---

## The count, final for this session

**Nineteen items** (numbered 1–15 and 17–20; there is no 16). Grouped by what
answering one costs you:

| | Items | What it takes |
|---|---|---|
| **Money that is wrong or unsettled** | 1 · 19 · 20 | one ruling each — item 1 is wrong in the product **today** |
| **A single word of permission** | 6 · 10 · 17 | "yes" |
| **Keep what we built, or change it** | 5 · 12 · 13 · 15 | either answer is cheap; we built the safer one and said so |
| **A name or a vocabulary** | 3 · 14 · 18 | nobody can invent these without minting an id you cannot look up |
| **A behaviour with two lawful answers** | 2 · 4 · 8 · 11 | a lane declined to choose for you |
| **Build a check we specified and never built** | 9 | yes/no |
| **Ratify a figure** | 7 | confirm **+174 kWh** is the right thing to show a clerk |

**Nothing here blocks work that is already moving.** Every wave that could ship
without a ruling has shipped. These are the ones where answering wrong in code
would have been worse than waiting.
