# J-PAY-lockbox-morning — a grocery store's file, with the store's own column names, and twenty-three rows a person has to answer

---
id: JPAYLOCKBOX
tier: 1
rules: [BR-PAY-023, BR-PAY-033, BR-PAY-021, BR-PAY-010, BR-MET-096, BR-MET-090]
stories: [US-PAY-003, US-PAY-001, US-LED-001]
---

<!-- CR-135 phase 1 `P1.14`, authored 2026-09-22 by lane P1-C.

     ⚠ **THE FILE IS NAMED FOR ITS ID, AND THAT IS A RULE RATHER THAN A STYLE.**
     `G12` check 3 matches a Playwright spec to a journey BY FILENAME, and the
     catalogue names files after ids — so a file called
     `J-PAY-lockbox-morning-…` declaring some other id can never have a spec
     found for it. That is `DEF-QAE-6208`, eight files that cannot be activated
     at all, and one of them was the sibling journey `JPAYWRONGACCT` written
     eight hours before this one. **`J-PAY-lockbox-morning` is not a legal id
     either way**: `g12_journeys.VALID_JOURNEY_ID_RE` is `^[JT][A-Za-z0-9]*(?:-\d+)?$`,
     which takes no interior hyphen, so the task table's name is a TITLE and
     `JPAYLOCKBOX` is the id. Both appear in the heading above so a reader
     searching for either finds this file.

     ⚠⚠ **AMENDED 2026-09-23 BY LANE ONEPATH — THE TWO BLOCKERS BELOW ARE
     CLOSED, AND THIS JOURNEY IS STILL NOT ACTIVATED. Those are two different
     statements and both are true.**

     **What was blocking, and what it turned out to be:**

       · `DEF-PAY-6212` — the payments list served no `origin`. **FIXED in
         `2.334.0`.** `selectors.payment_row` carries `origin`, `PaymentRow`
         declares it, and S33 draws the Source column and its filter.
       · `DEF-PAY-6213` — *"a payment carries NO link to the run that created
         it … the run and the row live only inside the idempotency key"*.
         ⚠ **THAT SENTENCE WAS FALSE AND IT IS LEFT HERE RATHER THAN QUIETLY
         REWRITTEN.** `import_run_rows.created_record_id` — its own comment
         reads *"what it made, for rollback"* — has named the payment each
         imported row created since the eighth import target landed, and
         `_load_payments_rows` sets it exactly as the accounts and parts
         loaders do. It was a READ that was missing, not a link that did not
         exist. **FIXED in `2.334.0`**: metering publishes
         `created_record_runs`, payments reads it through `metering_seam`, and
         the Batch column shows the run's number. A claim of ABSENCE needs the
         same evidence as a claim of presence, and it is cheaper to check.

     ⚠⚠ **AMENDED AGAIN 2026-09-23 BY LANE P01-FINISH — THE WALK HAS NOW BEEN
     RUN.** The paragraph that stood here said *"a journey first seen green is
     a journey nobody has proved"* and asked the activating lane to boot the
     stack and watch **B** and **G** fail first. Both were done, in that order,
     and this is what it cost and what it found.

     **How it was run, so it can be run again:**
       · `10-scripts/proof-db.sh clone p01finish` — a REAL PostgreSQL 16, which
         is the only place checks **B** and **G** exist (CLAUDE.md law 14);
       · Django on `127.0.0.1:8311`, `vite build` → `server.mjs` on `:8312`,
         signed in as `dana@brazosbendutilities.com`, Chromium at 1440×1000;
       · `10-scripts/jpaylockbox_seed_store_file.py` cuts the store's file and
         writes a MANIFEST of every figure it produced;
       · `10-scripts/jpaylockbox_walkthrough.mjs` walks the nine steps and
         reads checks **M** and **N** off the rendered page;
       · `10-scripts/jpaylockbox_readback.py` asks the DATABASE for **A**–**H**
         and refuses to run on SQLite by name.

     **⚠ THE FIXTURE IS 95 ROWS AND NOT 1,431, AND THAT IS A CORRECTION TO
     THIS DOCUMENT RATHER THAN A SHORTCUT.** `seed_demo` ships `brazosbend`
     with **72 accounts**. 1,408 clean rows would mean about twenty payments
     per household in one weekend and — worse — would make check **C**
     unjudgeable, because almost every row would land as credit on an account
     with no bill. So the file is **one clean row per account (72)** plus this
     journey's own **twenty-three** problem rows, and every assertion reads the
     manifest. The journey already said which of the two wins: *"every
     assertion below is written against the FIXTURE, never against a number."*

     **⚠ AND ELEVEN ACCOUNTS ARE GIVEN AN `external_ref` AS FIXTURE PREP.**
     `payments.import_writer.match_account` matches a payer name against ONE
     thing — an account's legacy reference, *"where the 'number' was often the
     household's name"*, in its own words — and `seed_demo` sets none. Without
     them all eleven name-only rows are refused `no_identifier` and the
     `PAY.NAME_ONLY_MATCH` rung this journey exists to test is never reached.

     **WHAT THE WALK FOUND, and check B is the one it was written for:**

       · **B FAILED.** Every one of the 72 payments created from a file dated
         `09/19/2026` and `09/20/2026` was stored `posted_at = cleared_at =
         2026-09-23`, **the day of the import** — the exact harm `BR-PAY-033`
         and `OQ-131`'s ruling exist to prevent. `_payment_moment` tested
         `hasattr(value, "year")`, and a stage-2 date cell is an ISO **string**,
         so `paid_at` was `None` on every row and the writer fell back to the
         operator's business day. `DEF-PAY-6294`, **FIXED**; B now reads *72 of
         72*.
       · **G PASSED, and was watched fail first.** `--prove-red` runs the same
         probe without the loader's savepoint: *with the savepoint: kept 2 ·
         WITHOUT it: aborted: InternalError*. That failure does not exist on
         SQLite, which is the whole of law 14.
       · **M PASSED after a second fix.** The Source column draws `Post` on
         every imported row — and **the filter beside it did nothing at all**:
         a real click left the box unticked, the address unchanged and the
         pager at `1–50 of 146`, which is every payment the tenant has. So did
         Status and Type. `DEF-PAY-6293`, **FIXED** — the page serialised its
         state through a config that declared no filters. **Measured again
         afterwards, in the browser:** the tick sticks, the address becomes
         `?…&f.origin=import`, and the pager reads **`1–50 of 72`** — exactly
         the payments this run created, and every Source cell on the page
         reads `Post`.
       · **N PASSES ON THE LIST AND CANNOT BE PERFORMED ON THE RECEIPT.** Every
         Batch cell reads `IMP-260923-02`, which is this run's number. The
         check says *"assert the number the RECEIPT showed"* — **the receipt
         prints no number at all** (`DEF-MET-6290`). N is asserted against the
         Imports list until it does.
       · **FIVE MORE, ALL FILED, NONE WORKED AROUND:** the receipt's figures do
         not add up to the file — 72 loaded + 11 rejected over 95 rows, with
         twelve on neither side (`DEF-MET-6287`) · stage 3 promises *84 will
         load* for a file the writer refuses 12 of, which is the `DEF-544`
         shape its own neighbour's comment names (`DEF-MET-6289`) · a payments
         run shows premises and units copy, *"72 of the 72 payments created
         took no services from the unit they sit under"* (`DEF-MET-6288`) ·
         the mapping picker offers *— ignore —* twice (`DEF-MET-6292`) · and
         the file **as the store actually writes it** cannot be imported at all
         (`DEF-MET-6291`, below).

     **⚠ THE FIXTURE TABLE ABOVE DESCRIBES A FILE THIS PRODUCT REFUSES, AND
     THAT IS THE SINGLE MOST USEFUL THING THE WALK PRODUCED.** Run as written —
     `PAID` with *"a leading `$` and thousands separators"*, `WHEN` with
     *"the store's own two-digit year"* — stage 3 reads **95 rows checked · 0
     will load · 95 blocked**, for two independent reasons: the comma is
     stripped and the `$` is not, and `DATE_FORMAT_PATTERNS` offers no
     two-digit-year slash format at all, so `09/19/26` matches nothing. The
     screen's own advice — *"change the format in Settings › Regional"* — names
     a remedy that does not exist for this file. **So the seed script emits TWO
     files and the walk runs BOTH**: `…-as-sent.csv` is the finding, and
     `…-repaired.csv` — no currency symbol, a four-digit year — is the hand
     edit a clerk must make to every row before the other thirteen checks can
     be reached at all.

     **`PAY-` ids in the *what must be TRUE* tables are shorthand.** The real
     keys are `payments.import.account_not_on_file` and
     `payments.import.name_only_match`; the stage-3 rule codes
     `PAY.ACCOUNT_ON_FILE` and `PAY.NAME_ONLY_MATCH` are real and are in
     `import_rules.PAYMENTS_RULES`.

     **`WHEN` maps to `paid_on`, not `paid_at`.** The fixture table above says
     `paid_at`; that is the PAYLOAD key the adapter produces, and the column a
     clerk maps to is `paid_on` / *Date paid*.

     **THE CANONICAL RUN, for anyone checking this record.** Fixture 95 rows
     (72 clean · 9 naming an account we do not have · 11 name-only · 3 with a
     bad amount). Stage 3: *95 checked · 84 will load · 11 blocked · 11 carry
     a warning*. Stage 4's dry run repeats *Will create 84 · Rows rejected 11*
     and demands an approval, because 11 of 95 is past the 5% bar. Receipt:
     *Loaded 72 · Rejected 11 · Flagged for review 11*. Run `IMP-260923-02` on
     the Imports list with its file name, its clerk and its three counts, and
     **no rollback control anywhere** (check **L**). Twelve checks run: **ten
     from the database, two off the screen, all twelve pass, and two were
     watched fail first.**

     ⚠ **THERE IS STILL NO `JPAYLOCKBOX.spec.ts`, DELIBERATELY.** What exists
     is a re-runnable pair of scripts and a recorded run. A Playwright spec is
     the next lane's, and it now has something it can be written against:
     nine steps whose selectors are known, a fixture that builds itself from
     the tenant, and twelve checks that have been seen to pass with two of
     them seen to fail first.

     ⚠ **THIS IS NOT `J14` AGAIN.** `J14-lockbox-day.md` is a tier-2 walk of one
     physical DAY of money — counter receipts, a 40-row file, deposit batches,
     the bank statement and a −5.00 difference — and its import step is one row
     of its table. This journey is the IMPORT itself, stage by stage, on the
     runner `P1.1`–`P1.5` put the payments target onto: **the store's own column
     names, the mapping a person does once, the twenty-three rows the product
     refuses to guess at, and the commit.** J14 asks *did the day tie out*; this
     one asks *can a clerk get a strange file into the books without guessing*. -->

**Fixture.** Tenant `brazos-bend`, Monday **2026-09-21, 08:40**. Ruiz Grocery
collects utility payments over its counter and emails a file every weekend. It
is a CSV of **1,431 rows**, and **not one of its column names is ours**:

| the store's column | what it holds | our field |
|---|---|---|
| `CUST REF` | what the payer wrote on the stub | `account_ref` |
| `PAID` | the amount, with a leading `$` and thousands separators | `amount` |
| `WHEN` | `09/19/26`, the store's own two-digit year | `paid_at` |
| `TILL SLIP` | the store's receipt number | `reference` |
| `NAME ON STUB` | what the payer wrote, often not the account holder | `payer_name` |
| `STORE` | which branch took it | — (no field; it is not dropped silently, see step 3) |

⚠ **THE FIGURES ARE THE FIXTURE'S AND NOT THE BLUEPRINT'S** (B14 rule 37 — a
figure drawn in a wireframe is an ILLUSTRATION). 4·1 draws `1,431 / 1,417 / 14`
and this journey uses **twenty-three** rejects because `P1.14`'s own task row
says twenty-three; every assertion below is written against the FIXTURE, never
against a number.

**The twenty-three, and they are three different problems on purpose:**

| how many | what is wrong | what the product must do |
|---|---|---|
| 9 | `CUST REF` names an account this utility does not have | **REFUSE** — `PAY.ACCOUNT_ON_FILE` |
| 11 | `CUST REF` is blank and only `NAME ON STUB` is filled | **FLAG for a person** — `PAY.NAME_ONLY_MATCH`; a name-and-amount guess never commits on its own |
| 3 | `PAID` is blank, or `0.00`, or `-12.40` | **REFUSE** — a refund is a different act with different books |

## The walk

| # | Step | Handoff contract to the next step |
|---|---|---|
| 1 | Open **Payments → Imports** | the run list renders; the ONE door out of it is `↑ Import`, at `/{tenant}/payments/imports/new` — `P1.5`'s outcome, and 4·1's *"Doors: The Imports tab. **1 door.**"* |
| 2 | Press **Import**, choose the **File** source card, drop the CSV | the runner opens at Extract with payments' own kicker; **Scan paper** is drawn as the fifth card and REFUSED with its reason (`P1.19` — our printed bill carries no remittance barcode yet) |
| 3 | Map the six columns | every one of the store's names is mapped by hand or by the saved template; **`STORE` is shown as an unmapped column and named**, because a column silently dropped is a fact the clerk never learns was thrown away |
| 4 | Choose the write mode | **Insert** is selected; **Insert & update** is drawn, disabled, WITH its reason (`P1.18` — overwriting a payment already on file is what hard rule 4 forbids). A clerk who has used the premises importer looks for it and finds it |
| 5 | Run the checks | **1,408 will load · 23 need a person**, split by the three reasons above, each row carrying the sentence it was refused for |
| 6 | Resolve the eleven name-only rows | each is answered by CHOOSING an account, never by accepting a guess; the nine unknown references and the three bad amounts are **taken out of this run**, not silently dropped — they leave on the failures download with their reasons |
| 7 | Commit | **stage 4 is the only stage that writes**, and nothing before it has touched the books |
| 8 | Read the receipt | it states what the run RECORDED: rows in, loaded, rejected (BR-MET-090 — the figures are the run's own, never recounted) |
| 9 | Land back on **Payments → Imports** | the run is on the list, newest first, with its number, its file name, who ran it, and its three counts |

## What must be TRUE afterwards

| # | Check | Why it is here |
|---|---|---|
| A | **1,408 payments exist and 23 do not.** Counted in the database with `app.tenant_id` set, not off the screen that just wrote them | the whole run, and hard rule 1 |
| B | **Every created payment's `posted_at` AND `cleared_at` is the day the STORE took the money** — 09/19 for a row whose `WHEN` says so — and NOT the day of the import | `BR-PAY-033` and `BR-PAY-021`. This is the check that earns the journey: dating a lockbox row by the day a clerk got round to importing it makes a customer late on a bill they paid on time |
| C | **Each payment is allocated under `BR-PAY-010`'s order**, and the bills it met are closed | the money has to land somewhere; a payment that exists and is applied to nothing is a credit nobody asked for |
| D | **Balanced journal pairs, written by the posting service and nothing else** | hard rule 5 |
| E | **One `audit_log` row per created payment** | hard rule 7 |
| F | **Re-uploading the same file writes NOTHING** and answers with the run that already exists | hard rule 6. `uq_import_runs_idempotency` guards the FILE and the per-row key guards the ROW, and they catch genuinely different things |
| G | **A crash between rows loses no row already written, and commits no row twice** | CLAUDE.md law 14 — the writer's savepoint. On PostgreSQL a failed statement aborts the whole transaction, and the naive `except: continue` passes the entire suite on SQLite and loses a morning's takings in production. **This check must be run on PostgreSQL or it is not run** |
| H | **`payments.origin = 'import'` on all 1,408 rows**, and `origin_is_derived` is false | `P0.1`'s check constraint, and an OBSERVED origin rather than a guess. ⚠ **Read from the DATABASE, with `app.tenant_id` set** — and that is now a SECOND reading of the same fact rather than the only one, because M reads it off the screen |
| M | **Every payment the run created shows `Post` in the Payments list's Source column**, and ticking Source → Post on the filter narrows the list to them | `DEF-PAY-6212`, closed in `2.334.0`. ⚠ **THE SCREEN AND THE DATABASE ARE TWO CHECKS AND BOTH ARE HERE ON PURPOSE.** H alone passed all the way through 2026-09-22 while the column reached no clerk — the fact was true and unreachable, which is hard-won law 2. ⚠ **AND THE FILTER HALF FOUND A SECOND DEFECT ON 2026-09-23**: the column drew `Post` correctly and the filter beside it did nothing at all, along with Status and Type (`DEF-PAY-6293`, fixed). A column you can read and cannot narrow by is half a feature |
| N | **Every payment the run created shows THIS RUN'S NUMBER in the Batch column** — `IMP-260923-02` on the walk of 2026-09-23 | `DEF-PAY-6213`, closed in `2.334.0`. This is `P1.14`'s outcome sentence — *"with their run"* — and it is the only check that ties a payment on the list back to the file it arrived in. ⚠ **THIS CHECK USED TO SAY *"assert the number the RECEIPT showed, never one recomputed here"*, AND THE RECEIPT SHOWS NO NUMBER** (`DEF-MET-6290`, filed by the walk). The reasoning behind that clause stands and is why this is not simply relaxed: a check that DERIVED the run number itself would agree with whatever the product happened to store. So it is asserted against the number the **Imports list** prints on the run's own row — a second surface, written by a different read — and it moves back to the receipt the day the receipt carries one |

## What must be REFUSED

| # | Check | Why it is here |
|---|---|---|
| I | A **name-only** row never commits on its own, however confident the match | `P1.12`, and `BR-PAY-023`'s own sentence. Two customers called J RIVERA is not a rare case in a town |
| J | A row naming an **account we do not have** is REFUSED and carries its reason onto the failures download — never skipped | a row that disappears is money nobody chased |
| K | A **zero or negative** amount is refused | a refund is a different act with different books |
| L | The run offers **no rollback**, on the list or on the receipt | `import_runs.rollback` refuses this target by name and `_load_payments_rows` creates no rollback point: a posted payment cannot be unwritten (hard rule 4). The way to throw a batch away is *Discard this batch* BEFORE the commit |

## The trap this journey exists to catch

⚠ **A WALK THAT ENDS AT THE RECEIPT PASSES OVER THE TWO CHECKS THAT MATTER.**
The receipt is written by the same code that did the load, so it will agree with
itself whatever happened. **B and G are the journey** — a run that loaded 1,408
rows and dated every one of them today is a run whose receipt says `1,408
loaded` and whose customers get late notices.

⚠ **THE OUTCOME SENTENCE IS NOW WHOLE — AND THE PARAGRAPH THAT STOOD HERE IS
LEFT IN OUTLINE RATHER THAN DELETED, BECAUSE IT IS THE RECORD OF HOW IT WAS
MEASURED.** It read, of `2026-09-22` at `67cb9e0c7`: *the one list* — TRUE;
*their run* — **NOT SERVABLE**; *Source · Post* — **TRUE IN THE DATABASE,
INVISIBLE ON THE SCREEN**. The middle verdict was a claim about the whole
schema made without grepping it, and it was withdrawn on 2026-09-23: the link
had been on `import_run_rows.created_record_id` the whole time.

**Measured again on 2026-09-23, on a booted stack rather than by reading:**

  · **the one list** — TRUE. Every created payment is an ordinary `payments`
    row on S33, and there is no second list anywhere.
  · **their run** — TRUE. Every Batch cell on the imported rows reads
    `IMP-260923-02`, this run's own number, served through
    `payments/metering_seam.py` (`DEF-PAY-6213`, `2.334.0`).
  · **Source · Post** — TRUE ON THE SCREEN. The Source column draws `Post` on
    all 72 (`DEF-PAY-6212`, `2.334.0`), and the filter beside it works as of
    `DEF-PAY-6293`.

**So `P1.14` is ACTIVE**, and it is active because the walk was run rather than
because the sentence was re-read. ⚠ **What is NOT claimed:** the receipt still
prints no run number (`DEF-MET-6290`), so check **N** is asserted against the
Imports list and says so out loud; and the receipt's own arithmetic is still
short by twelve rows (`DEF-MET-6287`), which is filed and deliberately NOT
worked around here — a journey that adjusted its own expectation to match a
receipt that does not add up would be the shape hard-won law 7 calls *looking
at the wrong thing*.
