## CR-072 — *"All the request coming from the portal should go in Service request"* — and the one place it does not

**Status: RULED, and the direction came with its own permission to widen.**

⚠ **THIS NUMBER WAS BRIEFLY USED FOR SOMETHING ELSE EARLIER THE SAME DAY AND IS NOT A COLLISION.** The
*"Connection = Account"* ruling was written as a file called `CR-072`, then folded into `CR-070` as `§W`
by PO instruction (*"it should be part of CR 70 itself"*). That file was **never entered in the change
register**, and the register's *"next free number"* stayed at `CR-072` throughout — deliberately, and
recorded at the time. This is the first change to actually take the number.

### CR-072 · 0 · CAPTURE — the Product Owner's words, verbatim

Said 2026-09-04 while looking at the portal's front page (`CWP-001`) on a live tenant,
`smartbillhub.bynry.com/silver-creek-water1/portal`:

> *"all the request coming from portal should go in Service request. if we have to icnrease the
> defination of Service request we should do it"*

**Two sentences and the second one is the unusual part.** Requesters normally state a requirement and
leave the cost to us. This one states the requirement *and pre-authorises the expensive answer* — if the
existing record cannot hold what the portal produces, widen the record rather than inventing a second
one. That is the same instinct as `CR-070 §W` (*"you cannot have two differnt screen"*) and
`BR-MET-1161` (one home for an address), and it is worth naming as a pattern: **the PO keeps refusing a
second place to look at one fact.**

### CR-072 · 1 · CLASSIFIED

A **requirement**, not a defect — nothing signed says otherwise and no rule is being reversed. It is
**not urgent** in the sense that nothing is broken for a customer today; it is urgent in the sense that
`CR-068` waves E and P are unbuilt and would repeat the shape if this were left unruled.

### CR-072 · 2 · WHAT THE PRODUCT ACTUALLY DOES TODAY, MEASURED

**The ruling is ALREADY MET for three of the portal's four shapes**, and saying so plainly matters more
than claiming a large change:

| Portal flow | What it writes | Meets the ruling? |
|---|---|---|
| **Report a problem** (`CWP-006`) | a `service_requests` row **AND** an `interruptions` row | ⚠ **partly — see §3** |
| **Start service** (`CWP-008/009`) | a `service_requests` row, plus a `portal_consent` row | ✅ yes |
| **Something else / quick ask** (`CWP-015`) | a `service_requests` row | ✅ yes |
| **Track** (`CWP-012`) | nothing — it is a read | n/a |

`apps/portal/write_points.py` already declares `service_request` as one of exactly four write points and
names `service_request_service.raise_service_request` as its one function; `G81` fails a fifth write from
any file in the module. **So the architecture the PO is asking for is the architecture that exists.**

Two portal writes are **not requests and are not in scope**: a **payment** (money, not a request) and a
**self-submitted meter reading** (a measurement, not a request). Reading the ruling to cover those would
put a bill payment on a clerk's worklist. Stated here so a later lane does not read the absence as an
oversight.

### CR-072 · 3 · THE ONE PLACE IT DOES NOT HOLD, AND WHY IT IS SUBTLE

**A problem report creates TWO records and hands the stranger the wrong one's reference.**

`apps/portal/services.py::_report` opens one transaction and writes:

1. a `service_requests` row, through `customers.service_request_service.create_from_portal`; then
2. an `interruptions` row, through `metering.interruption_service.create_interruption`, carrying a
   pointer back to the request.

and then returns **`interruption.reference`** — an `RP-26-0412` — as *"the whole record of the
interaction"* for somebody with no account. The `SR-` number the same call just created is deliberately
withheld (`BR-CWP-024`: *"one reference, and it is theirs"*).

**So a clerk has two rows and a customer has the number of the one that is not the request.** That is
precisely the duplicate-destination shape the PO has now objected to three times.

⚠ **BUT `interruptions` IS NOT SIMPLY A DUPLICATE, AND PRETENDING IT IS WOULD LOSE REAL DATA.** It
carries **six facts `service_requests` has no column for**: `kind` (a leak, no water, a missed
collection), `status` (its own transitions, which a crew moves), `resolved_at`, `affected_area` (the
street-and-number-range rule that answers *2 addresses, 3 units*), `expected_back_on`, and a
`premises_id` a **clerk** resolves from free text later.

### CR-072 · 4 · THE READING, AND IT IS A BUILD JUDGMENT RECORDED RATHER THAN A QUESTION PUT BACK

`interruptions` is **two different things wearing one table**, and separating them is what makes the
ruling implementable without losing anything:

* **(a) THE REPORT** — *a stranger said there is water coming up through the pavement outside 1412*.
  That is a **request**: somebody is asking the utility to do something. Under this ruling it **is** a
  service request and the `SR-` number is what the person is given.
* **(b) THE CONFIRMED INTERRUPTION** — *supply is off on Elm St between 1400 and 1500, 3 units affected,
  expected back by 18:00*. That is **not a request at all.** It is the utility's own operational record,
  opened by a clerk who has decided the reports are real, and it may gather **many** reports — which is
  exactly what `already_reported_street` exists to notice.

**One report is one request. Many requests may point at one interruption.** That is the shape the data
already wants: today the FK runs the wrong way round (`interruptions.service_request_id`, one-to-one),
which is what forces a second row per report.

**WHAT THIS MAKES CONCRETE:**

1. **The guest is handed the `SR-` number.** One reference, from the record that is the request. The
   `RP-` series stops being a customer-facing thing.
2. **A report no longer creates an interruption.** A clerk opens one when the reports are real — which is
   also the honest answer to *"is this an outage?"*, a question a stranger's form cannot settle.
3. **`service_requests` widens to hold what a report needs** — the PO's own second sentence. At minimum
   `kind` (what sort of problem) and the reporter's own words, which the row already keeps in
   `what_they_said` and `address_as_given`.
4. **`interruptions` keeps its six operational columns and loses its one-to-one FK to a request**,
   gaining instead a link the other way so many requests can attach to one.

### CR-072 · 5 · WHAT IS ALREADY BUILT AND IS NOW WRONG (change-process step 4)

* **`CR-068` wave B is shipped and live.** Its `RP-` reference is on screen, in eleven catalogues, in a
  browser walkthrough of 32 assertions, and in `test_us_cwp_007_report.py`. This is a **shipped
  customer-facing behaviour**, so the change is a supersession with a migration, not a correction.
* **`interruption_no` / the `RP-` series is seeded per tenant.** A tenant provisioned before today has no
  counter (`DEF-CWP-3735`); retiring the series customer-side removes that whole class of problem.
* **No lane is building on it right now.** Waves B, C and D are closed; waves E and P are unstarted, which
  is why this is being ruled now rather than after they repeat the shape.
* **No data is lost and none needs migrating in production** — the only rows are sample and walkthrough
  fixtures.

### CR-072 · 6 · WHAT IS *NOT* IN SCOPE, STATED SO ABSENCE IS NOT READ AS OVERSIGHT

* A **payment** and a **self-read** stay where they are; neither is a request.
* `BR-CWP-026` is untouched: **no guest write changes an account**, and widening the request record does
  not weaken that.
* The clerk's own interruption screen is unchanged in what it shows; only where its rows come from moves.

### CR-072 · 7 · SIZE, AND THE ROLLBACK

One wave. Backend: one migration widening `service_requests`, one reversing the FK direction on
`interruptions`, and `_report` reduced to a single write. Frontend: `CWP-007` shows the `SR-` number, and
the eleven catalogues lose one string and gain none. **Rollback: the migration is additive on
`service_requests` and the FK reversal is a new nullable column beside the old one, so the previous
behaviour is a code revert with no data loss.**

---

### CR-072 · 8 · CLOSED — built and shipped as `2.140.0`, 2026-09-04

**Status: DONE.** One wave, as sized. The decision log entry of 2026-09-04
(*"CR-072 IS BUILT — the report is the request, and a clerk decides what is an
outage"*) carries the five judgments made where the rules ran out; this section
records only what §7 got WRONG, because that is what a later lane needs from a
closed CR.

**§7 SAID THE ELEVEN CATALOGUES *"LOSE ONE STRING AND GAIN NONE"*. MEASURED:
THEY LOSE NONE AND GAIN SIX.** There was never an `RP-`-shaped string in a
catalogue — a reference is data, not copy — so nothing was there to lose. What
the change actually needs is words for the clerk's new act: the absence sentence
(*"Nobody has opened an interruption for this yet"*), two commits (*Open an
interruption ✓*, *Add to {{reference}} ✓*) and three refusals, in eleven
languages. **All additive; the diff is `+6` per file and `-0`.**

**§7 SAID THE FRONTEND WAS *"`CWP-007` SHOWS THE `SR-` NUMBER"*. `CWP-007`
NEEDED NO CHANGE AT ALL** — it renders whatever `reference` it is handed. The
screen that DID need building is the one §7 does not mention: **the clerk's
Interruption section**. Without an *Open an interruption* control it would have
404ed on every report forever, because the thing that used to create its row was
the guest form this change removed. That is hard-won law 2 arriving in advance
of the defect rather than after it, and it is the single largest piece of work in
the wave.

**§3'S SIX COLUMNS SURVIVED EXACTLY AS PROMISED.** `kind`, `status`,
`resolved_at`, `affected_area`, `expected_back_on` and `premises_id` are
untouched on `interruptions`; nothing was lost by moving the report out.

**ONE THING §7 DID NOT SEE AT ALL, AND IT WOULD HAVE SHIPPED SILENTLY.**
*"Someone has already reported this street"* is a sentence `CR-068` wave B
shipped, and the scan behind it read `interruptions`. Reports do not write that
table any more, so left alone it would have answered nothing for every real
second report — with `tsc`, every unit test and every gate green, because no
check asserts that a sentence still has data behind it. It reads open REPORTS
now, and a confirmed interruption when there is one.

**THE ROLLBACK, RESTATED NOW THAT IT IS REAL.** `customers/0040` is additive;
`interruptions.service_request_id` is still there and still nullable, read and
written by nothing. Reverting the code restores the previous behaviour with no
data loss and no down migration. **The wave that removes that column is the
first one to touch `interruptions` after this ships** — named in the model's own
docstring so its removal is a plan and not a discovery.


### CR-072 · 9 · WHAT WAS PROVED, AND THE ONE THING THAT WAS NOT

**Proved, and each on the harness that will actually run it (hard-won law 7, both halves):**

* **39 backend cases**, 31 on the default SQLite suite and **8 on real PostgreSQL 16**. The
  PostgreSQL half runs under the **non-superuser `sbh_rls_probe` role** — the dev role is a superuser
  and bypasses row-level security unconditionally, so a green under it proves nothing — and reads
  `pg_class` for **both** `relrowsecurity` and `relforcerowsecurity`.
* **Proved RED first, twice, in the dangerous direction.** With `NO FORCE` on `service_requests`
  exactly ONE case fails (*"RLS is not FORCED, so the owner bypasses it"*) and the other four still
  pass — because the probe role is not the table owner, which is precisely why that case reads both
  flags. With row security DISABLED all five fail, including *"a query with NO tenant context
  returned 1 row(s)"* and *"LEAK — Oak Ridge read Pine Hill's report kind"*. Restored: 5 passed.
* **11 frontend cases** on the clerk's Interruption section, rendered through the real component with
  the real catalogue — a test file the component's own trace header had cited since the day it was
  written and which did not exist (`DEF-CWP-3743`).
* `tsc --noEmit` clean; `makemigrations --check` clean on the merged tip.

⚠ **THIS SECTION SAID *"WHAT WAS NOT RE-RUN"* UNTIL 2026-09-04 10:2x, AND IT IS NOW RUN.** The text
below is kept rather than deleted, because it is the honest record of a claim that stood unproved for
about an hour, and law 1 is about exactly that gap. **Result: `cr068-b: all checks passed`, exit 0,
46 assertions, 0 failures**, in a real Chromium against a real seeded PostgreSQL. The assertions that
had only been amended are the ones that matter, and each read back green:

* `the reference reads SR-26-0001` — the stranger is handed the REQUEST's number;
* `the gas form consumed no number: SR-26-0001 → SR-26-0002 (gap 1)` — measured by the SERIES rather
  than by counting rows, so *"it wrote nothing"* is proved by what the next reference is;
* `a fresh report has NO interruption, and the section says so rather than 404ing` — the clerk's new
  panel, the screen `CR-072 §7` did not know it needed;
* `the clerk's own record carries the RP- number — a clerk's vocabulary, never the guest's`;
* `the response body carries eight keys and no customer field`.

⚠ **AND IT TOOK THREE DEFECTS TO GET THERE, WHICH IS THE PART WORTH READING.** The walkthrough was not
hard to run; it was hard to *reach*. `proof-db.sh` defaulted to an interpreter that cannot import this
project, and reported the failure one command later as *"the template is 261 migrations behind"*
(`DEF-GOV-3753`). Then `seed_portal_demo` refused with `VAL-005 (metering.premises_owner.category_
unknown)` because the portal fixture held **two unscoped querysets** and, under a seeding role that
bypasses RLS, read another utility's rows (`DEF-CWP-3757`) — right by accident on an empty database and
fatal on the realistic one a proof template exists to provide. Both had to be fixed before a single
assertion could run. **The lane that shipped this change was not wrong to record the walkthrough as
unrun: the road to it was blocked by two faults in the tooling, neither of which named itself.**

**What is still not proved, stated rather than rounded up:** section 10's response-time loop drives the
Django dev server hard enough to reset connections (`ERR_CONNECTION_RESET`, repeatedly). Its assertions
are not among the 46 and the figures it prints are not evidence. That is a harness limit, not a product
one, and it belongs to whoever wires a real server into the render-checks.

---

**THE RECORD OF THE HOUR IT STOOD UNPROVED, kept deliberately:**

⚠ **WHAT WAS NOT RE-RUN, AND SAYING SO IS THE POINT (law 1).**
`10-scripts/render-checks/cr068-b-report-and-track.mjs` — the 32-assertion browser walkthrough — was
**AMENDED and NOT EXECUTED**. Six assertions changed (`/^RP-/` → `/^SR-/`, the `SR-`/`RP-` exclusion
inverted, the guessed references, the gas-form gap comment) and **one step was added**: the clerk
pressing *Open an interruption* before any status can move, which is the ruling itself. A seeded
database was built for it (`sbh_tpl_0d08008d`, migrated forward in 157s) and `seed_portal_demo`
did not complete under the machine's load in the window available.

**So the walkthrough's own claim is a claim, not a proof, until somebody runs it** — which is exactly
what hard-won law 1 exists to stop being written the other way. The command is in the script's header
and the database is already built:

    10-scripts/proof-db.sh clone cwpb            # sub-second, stamped 0d08008d
    …/manage.py seed_portal_demo                 # then the two servers, then the script

**Nothing in the amendment is guessed:** every changed assertion matches a backend case that DID run,
and the new step matches `test_cr072_report_is_a_request.py`'s
`test_cr072_a_clerk_opens_one_and_the_report_reads_its_progress_through`.
