# The defect register, measured — 2026-09-05

**What this is.** Somebody asked how many bugs we actually have. The register
answers 674, and that answer is not trustworthy. This document says how far off
it is, shows the evidence, and explains why the number drifts so that the next
person does not have to work it out again.

Read this before planning from the register.

---

## 1 · The two numbers

| | |
|---|---|
| What the register claimed when this audit started | **678 open** |
| What it claims now | **674 open** |
| Rows this audit proved were already done, and closed | **8** |
| Rows this audit proved are genuinely still open | **9** |
| Malformed rows repaired | **1** |

The register did not fall by 8, because nine other lanes were filing new rows
the whole time this ran. That is normal and it is not the problem.

**The honest headline is not 674.** It is this: *of the open rows, roughly one
in ten describes work that has already shipped, and nobody can tell which ones
without reading the code.* The register is a good record of what was **found**.
It is a poor record of what is **outstanding**, and those are different
questions.

### What 674 is probably worth

Twenty-four open rows were drawn at random and checked against the code. Nine
could be settled conclusively. **One of those nine had already been fixed.**

That is about 11%, so the true open figure is probably in the low 600s rather
than 674. **The sample is small and the honest range is wide** — anywhere from
"barely any drift" to "a third of it" is consistent with one stale row in nine.
Nobody should quote a precise corrected total, including this document.

### Why this is much better news than the portal audit suggested

Earlier the same day, the portal's 67 open rows were checked and only **24**
were real — a two-thirds overstatement. It would be easy to assume the whole
register is that bad. **It is not, and the reason is worth understanding.**

The portal was built in a burst: many lanes, new screens, a few days, rows filed
and fixed within hours of each other. That is exactly the condition that
produces duplicate records of one fault. The rest of the register is older and
more settled, and it drifts far more slowly.

**So the rule of thumb is: distrust the open count most where the work is newest
and the lanes are most numerous.** A quiet module's open rows are mostly real.

---

## 2 · What is genuinely open

Counts below are what the register says today. Treat the module and severity
*shape* as reliable and the totals as roughly 10% high.

### By severity

| Severity | Open |
|---|---|
| critical | **0** |
| major | **0** |
| high | 159 |
| medium | 348 |
| low | 167 |

**There are no open critical or major defects.** There were three when this
started — all three had already been fixed and none had been closed. One of them
(`DEF-WRK-4027`) was stopping every PostgreSQL database on the branch from being
built at all; it was fixed at 17:10 and its row still said `open` hours later.

### By module

| Module | Open | of which high |
|---|---|---|
| rating | 79 | 14 |
| billing | 77 | 24 |
| metering | 73 | 12 |
| tenancy | 68 | 13 |
| customers | 59 | 17 |
| payments | 56 | 20 |
| governance | 56 | 16 |
| platform | 40 | 11 |
| platform-shell | 35 | 4 |
| notifications | 31 | 6 |
| ledger | 26 | 3 |
| work | 16 | 2 |
| integrations | 15 | 9 |
| everything else | 44 | 8 |

**Where the weight is: billing, payments and customers carry 61 of the 159 open
high-severity rows** — the money path. Rating, billing and metering carry the
largest raw counts, which is what you would expect of the three oldest and
busiest modules.

---

## 3 · The oldest high-severity items still open

These have been open longest. They are stated the way a person would say them.
The ones marked **verified** were confirmed against the code by this audit; the
rest are as the register describes them and have not been re-checked.

1. **A finished bill run still calls itself a draft.** (`DEF-171`, billing,
   since 16 Aug) — **verified.** A run can issue every one of its bills and the
   stored status never moves off `draft`, so a screen showing it titles every
   historical run *Draft*. The code says so about itself in
   `billing/api.py:955`; it is a known, documented hole rather than a surprise.

2. **Two histories can be written and never read back.** (`DEF-130`, rating,
   since 15 Aug) — **verified.** The record of which plan a unit was put on, and
   the record of rate-schedule versions, both accept writes over the API and
   refuse every read. Append-only histories that nothing can read are not much of
   an audit trail.

3. **The code tells the next engineer to rebuild a bug that was already fixed.**
   (`DEF-2220`, rating, since 28 Aug) — **verified.** The rate-resolution file's
   own header instructs whoever wires the chain to apply discounts before taxes
   and carries the old worked figure. Following the instruction re-creates a
   money defect that was fixed once already.

4. **The first dunning letter a utility can send addresses the customer as
   "——".** (`DEF-173`, notifications, since 16 Aug). The reminder builds its
   render context without the customer's name, so the greeting and the account
   both come out as a placeholder dash. This one goes to a paying customer's
   letterbox.

5. **A utility uploads its logo and picks its brand colours, and no document
   ever draws them.** (`DEF-195`, tenancy, since 17 Aug) — **partly fixed.** The
   settings screen now previews the mark, but the templates still exclude the
   logo token by name, so bills and notices remain unbranded.

6. **Thirteen ruled rules have no door.** (`DEF-135`, platform, since 15 Aug).
   The rules are built and tested; no human can reach them from any screen.
   Single read, payment plans and budget overrides are among them. This is the
   repo's own "built is not wired" failure, thirteen times, and it is the largest
   single block of finished-but-invisible work in the register.

7. **Money that is absent prints as $0.00, or as the word "undefined".**
   (`DEF-179` and `DEF-180`, payments and billing, since 16 Aug). The server
   deliberately refuses to send a zero where it means "no figure", and five cells
   on the deposit and bank screens turn that absence into a confident $0.00; two
   other screens print `undefined USD`. Both directions are wrong in front of a
   clerk who is reconciling cash.

8. **Five documented seams still make a fact up.** (`DEF-079`, billing, since 11
   Aug). They substitute a placeholder over tables that now genuinely exist, and
   one of them will let somebody delete a rate plan that has already been billed
   against.

9. **A hundred and one message keys are raised by shipped code and defined in no
   catalogue.** (`DEF-055`, platform, since 11 Aug). Where one of those fires,
   the user sees a raw dotted key instead of a sentence.

---

## 4 · What was closed, and on what evidence

Every closure below was confirmed by reading the code at the branch tip. None
was closed on a commit message alone.

| Row | What it said | Why it is closed |
|---|---|---|
| `DEF-WRK-4027` (critical) | A migration trigger PostgreSQL could not compile, so no database on this branch could be built | The migration carries a single `%` and a comment naming which substitution path it is on. Fixed in `5ab3d2df` |
| `DEF-2379` (critical) | A deployment with no document storage boots happily and only says so at bill issue | The boot check exists, is registered in `tenancy/apps.py`, and its test drives it to a verdict. `34ad19ba` |
| `DEF-WRK-4030` (major) | Two questions were answered on 4 Sep and the epic, plan and stories still called them open | Both now recorded as closed, and the two code stubs raise the ruling's own sentence instead of a question id. `eb7eb46b` |
| `DEF-070` (high) | The cash-only flag the NSF rule needs "has no column anywhere" | `customers/models.py:457` declares it; migration `0009` creates it. `3dd729fb` |
| `DEF-069` (high) | The NSF counter could not be incremented because customers published no seam | `customers/services.record_nsf()` does the increment and the flag trip in one transaction. `75c77858` |
| `DEF-098` (high) | The "already billed" lock on a meter read was unreachable because nothing called it | `billing/issue.py:2239` calls it. `5376b62a` |
| `DEF-3463` (low) | Three frontend suites red because two routes were added without the three lists that mirror the nav | All three carry both routes. `182ab7a0` |
| `DEF-3508` (medium) | The whole frontend suite passed and the runner still exited 1 | The offending call is now optional, with the reason in a comment. `1c620d60` |

### A near-miss worth recording

`DEF-2220` was almost closed on a search that returned zero hits. **The phrase
wrapped across two lines**, so the grep was a false negative and the row is
genuinely open. Nothing downstream would have caught that closure — the next
person would simply have believed it. **A grep that finds nothing is not
evidence that nothing is there**; it is evidence that one spelling is not there.

---

## 5 · What could not be settled, and what would settle it

Of 674 open rows, this audit conclusively settled **17** — eight closed, nine
confirmed open. **The remaining 657 are unsettled**, and that is the honest
state of them.

They fall into three groups.

**a. Needs someone to read the code (the large majority).** Most rows describe a
specific fault in a named file. Settling one takes ten to thirty minutes of
reading. There is no shortcut: mechanical matching of commit messages to rows
was tried here and is right about 40% of the time, which is worse than useless
for closing rows because a wrong closure is believed.

**b. Needs the product run.** Rows about what a screen actually shows cannot be
settled by reading at all — the repo's own hard-won law 6 says the only way is to
diff the running application against the prototype. That is a browser session,
not a grep.

**c. Needs a decision, not an investigation.** Some rows describe things that
were deliberately not built. They are not defects any more and should be
`wontfix` with the ruling quoted, but only the Product Owner can say so.

**The cheapest way to shrink 657 is by module, not by severity** — one person
reading one module's rows in one sitting shares all the context between them.
Billing's 24 open highs are the place to start, because that is the money path
and it is the largest single block.

---

## 6 · Why the number drifts, and what it costs

**The mechanism is one act split in two, and only the first half feels like the
work.**

A lane finds a fault and files a row. Later — often a different lane, sometimes
hours later — somebody fixes it. They write an honest commit message saying what
they fixed. They file **their own** row describing what they found. And they do
not go back and close the row that *reported* it.

That last step is skipped for a reason that is not laziness: **closing somebody
else's row means editing a file that ten lanes are writing to at once**, which
in this repo is a genuinely risky operation with its own dedicated tool and a
history of lost rows. Filing a new row is an append and is safe. Closing an old
one is an edit and is not.

So the same fault ends up in the register twice — once as an open report, once
as a closed fix — **and only the second one is honest.** The open count only ever
goes up for reasons that are not real.

**What it costs.** The open count is what the Product Owner plans from. When it
says 678 and the answer is nearer 600, the plan is built on work that does not
exist, and the items that *do* need attention are buried among rows describing
things that already work. The portal slice was worse: two-thirds of it was
finished work presented as a backlog.

**Why nothing caught it.** Every gate in this repo reads code, or documents, or
the register's *structure*. **Nothing read a commit message against the
register.** The repository had already written down, in plain English, that
`DEF-WRK-4027` was fixed — in the subject line of a commit — while the row said
`open`, and all 113 gates were green over it.

### The fix that is now in place: G113

`10-scripts/gates/g113_closure_drift.py` fails when a recent commit **asserts** a
defect is fixed and that defect's row still reads `open`.

* **Cost:** one `git log` over the last 400 commits plus one read of the
  register. Under two seconds, no network.
* **Precision was the whole design problem.** A first draft matched any
  fix-shaped word near a defect id and was right about 40% of the time — it read
  *"must not be used until DEF-195 is fixed"* and *"the day DEF-2967 is fixed the
  case goes red"* as closures, and both are the opposite claim. A merge gate that
  is wrong three times in five gets switched off. So it matches only asserting
  forms, judges the clause around the id rather than the whole message, and drops
  any clause a conditional word governs.
* **It carries a ratchet baseline** which ships **empty**, because the one
  occurrence it found was closed rather than baselined.
* **Proved RED through `run_gates`' own import path**, not by running the file
  directly — the distinction that `DEF-GOV-3733` exists to enforce. Against the
  register as it stood this morning it named `DEF-WRK-4027`; against the register
  now it passes.

**What G113 does not do, said plainly so nobody trusts it too far.** It does not
find stale rows in general. It catches only the case where the repo already told
us in writing. The other 657 still need somebody to read the code.

---

## 7 · Housekeeping findings

⚠ **THIS HEADING READ *"Two housekeeping findings"* UNTIL 2026-09-10, WHEN A THIRD
ARRIVED.** The count came out rather than being incremented: a number in a heading is a
pointer to a list, and this repository has now recorded five separate occasions on which
ratifying a thing and updating the pointer to it were two acts and only the first got
done.

### The malformed row — fixed

One row was unreadable. `DEF-WRK-4051` had 23 fields against a 14-column header,
so its `status` column landed on a fragment of its own title and read
`for the registry)`. Nothing could tell what the row said. **Its real status was
`fixed`.**

**The cause was not what the gate said.** G26 reported *"a raw newline in a prose
column splits one row into two"*. There was no raw newline. The row quotes some
route constants, and the quotes were written the way a programming language
escapes them — `\"` — where CSV escapes a quote by **doubling** it. A backslash
means nothing to a CSV reader, so the quote after it closed the field early and
everything past it was read as new columns. Ten times on one line.

Repaired, and G26's field-count violation is gone. **The general lesson: a tool
that appends a line somebody else serialised can introduce an escaping that is
correct for one format and fatal for this one, and every reader downstream sees
a *shorter* row rather than a *broken* one.**

### The category column — free text, now the register's THIRD controlled vocabulary

**PO ruling 2026-09-10:** *"we cannot manage what we cannot count"*.

`severity` and `status` have had controlled vocabularies for some time. **`category`
never did, and free text in a column nobody closes does not drift — it explodes.**
Measured that day: **2,395 rows carrying 1,016 distinct category strings**, with 579 of
the last nine days' defects sitting in 486 categories used three times or fewer.

**Twelve values now**, derived from the existing strings rather than invented, covering
99.7% of the rows already filed. `10-scripts/register_vocabulary.py` holds them beside
the other two; `g46` fails a row filed from **2026-09-11** onward that does not use one;
`file_defect.py` refuses to write one. **Nothing was rewritten** — the legacy rows are
COUNTED AND NOT CHECKED, and that count prints on every gate run so a ratchet that has
stopped moving is visible.

⚠ **AND THE FIRST THING THE VOCABULARY DID WAS OVERTURN THE ANALYSIS THAT PROMPTED IT.**
The census was proposed on the strength of *"32% of defects are a screen not matching its
design, and only 6% are wrong logic"*. **Counted, it is 10.8% and 19.2%.** The largest
category is **a check that does not check, at 26.5%**. Both original figures came from
bucketing free text by keyword, and two readers doing it independently disagreed by
twenty points on the largest bucket — which is precisely the argument for the column
being closed, made by the column itself.

### The status vocabulary — nine values, and it should be six

In use today:

`fixed` (1123) · `open` (674) · `closed` (23) · `partially-fixed` (22) ·
`fixed-in-part` (12) · `duplicate` (6) · `invalid` (5) · `wontfix` (5) ·
`reported` (2)

**Three pairs say the same thing twice:**

* `partially-fixed` and `fixed-in-part` are the same state under two spellings.
  Keep **`partially-fixed`** — it is used nearly twice as often.
* `reported` and `open` are the same state. Keep **`open`**; `reported` has two
  rows and no distinct meaning.
* `closed` and `fixed` overlap. `fixed` means the fault is gone; `closed` is used
  where a row was retired for some other reason, which is what `wontfix`,
  `duplicate` and `invalid` already say more precisely. Keep **`fixed`**.

**The recommended vocabulary is six values:**
`open` · `partially-fixed` · `fixed` · `wontfix` · `duplicate` · `invalid`

**Do not rewrite 1,872 rows to enforce this.** A mass rewrite of a file that ten
lanes append to is precisely the operation this repo has lost work to more than
once, and the benefit is cosmetic. The right sequence is: stop the tools emitting
the losing spellings, let the 37 affected rows be corrected as they are touched
for other reasons, and drop the retired values from the gate's vocabulary only
when the count reaches zero. That is a ratchet, and it costs nobody a risky
commit.

---

## 8 · One thing found on the way

The full gate suite currently reports **75 PASS, 32 FAIL, 5 SKIP — merge
blocked**. That is separate from anything in this document and is not reflected
in the register's open count, but anybody planning from these numbers should know
the branch is not green. `G78` in particular is red on four new violations in
`apps/work` that postdate the row which recorded the last ones.
