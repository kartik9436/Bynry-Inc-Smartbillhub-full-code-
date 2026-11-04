# Capture step 4 — Documents, built to the drawing, and the door that was opened

**Built at:** `v2.311.5` · 2026-09-19
**Benchmark:** `05-prototype/02 Accounts Menu Blueprint.pdf`, entry **06 Service request
capture**, **page 78 (TOP)**, read **AS A PAGE IMAGE** at scale 2.6 and again, cropped,
at scale 6 (B14 rule 42 — *"When you use images to create screens your accuracy is
higher; hence dont create screens using only Text"*).
**Scope:** step **4** of `ServiceRequestCapturePage.tsx`. Steps 1, 2, 3, 5 and 6 were not
touched.

⚠ **THE LABELS ON THIS PAGE ARE NOT IN THE PDF'S TEXT LAYER.** `DOCUMENT`, `REQUIRED`,
`UPLOADED BY`, `Attaching one`, `Required on this request` — every one is vector art. A
text search of the document returns nothing and would report that this screen is not in
the blueprint at all.

---

## 1 · THE HEADLINE — a clerk can attach a real file, and could not yesterday

The store landed earlier the same day and **deliberately left the control shut** for this
lane to open. It is open.

A clerk on step 4 chooses a document type, picks a file off their machine, types what it
proves, ticks *Required on this request* and presses **Attach a file**. The bytes go
through `service_request_documents.file_document` to `tenancy.document_store`, which
shrinks losslessly where it can, writes a sha256, takes the seven-year object lock and
returns. The row comes back in the drawn table reading the file's **name and size**, the
clerk's **name** and the date, and the state **Not checked**.

**Proved twice, because a row in a table is not a file:**

| What | How | Result |
|---|---|---|
| The screen | `10-scripts/po20260919_request_step4_documents_walkthrough.mjs`, Chromium at 1280 against Django + PostgreSQL | **72 PASS · 0 FAIL** |
| The same walk against a bundle built from the pinned tip | the six-commits-earlier build, served beside it | **13 PASS · 23 FAIL** |
| The bytes | `10-scripts/po20260919_request_step4_readback.py`, through the module's own published door | **8 PASS · 0 FAIL** |

The readback is **expected-value driven, not self-consistent**. Hashing whatever the
store returns and comparing it with itself would pass over a file of zero bytes. The walk
writes a body containing its own run tag; the readback composes that string
independently and compares. `sha256 6091edf4c4eed589` on both sides, 50 bytes, and the
row's own `size` column agreeing with the bytes returned.

It also asserts **the refusal**: the walk's second row has no file, and the store must
RAISE for it rather than answer, because a store that hands back bytes for a row with no
file is a store that invents files. Red-proved three ways — exit 1 against the tip run's
request, which has no attachment at all; exit 1 on a tag that does not exist; exit 0 only
on the real one.

---

## 2 · What was built

| Drawn (p078) | Before | Now |
|---|---|---|
| a TABLE — `DOCUMENT · REQUIRED · FILE · UPLOADED BY · STATE` | **nine tick-boxes** over `form.documents` | the five drawn columns in the drawn order, read from the SERVER |
| `FILE` shows name AND size | nothing — there was no file | `driving-licence.pdf · 50 B`, and a second line *from 3.1 MB* when the store shrank it |
| `UPLOADED BY` shows who and when | nothing | the person's NAME and the date, in the tenant's format |
| `STATE` — `Verified` / `Not checked` / `Nothing attached` / `Rejected · unreadable` | a tick or nothing | all four, and the rejection reason beside it |
| chips `All · Required · Missing · Rejected` | built, narrowing the tick-list | built, narrowing the drawn ROWS |
| `Attach a file` | **disabled**, under a refusal | **live** |
| `Add another document` | absent | built — the same route without bytes |
| `Attaching one`: type · file · what it proves · `Required on this request` | absent | all four |

⚠ **THE TABLE READS THE SERVER AND NOT `form`, AND THAT IS THE ROUND TRIP RATHER THAN A
REFACTOR.** The tick-list was component state that a draft save never read back, so a
clerk who ticked three documents and left the wizard lost all three, and one who reopened
a saved draft saw an empty list while the server held the rows. The table reads
`draft.documents.documents`, which is why a document now survives being saved, the wizard
being closed and the draft reopened — each of which the browser walk performs.

**Two fields were added to the payload for the drawn columns:**

* **`uploaded_by_name`** — `UPLOADED BY` draws a PERSON and the payload carried only
  `uploaded_by`, a uuid. A screen obeying the drawing would have printed the uuid into
  the cell, which is B14 rule 31 (*"no Databse ID on screen - that is a rule"*).
* **`file_present`** — see §4. `attached` is `bool(storage_ref)` and answers True for all
  six broken beta rows.

---

## 3 · The three things in that drawing that are NOT screen copy

1. **The amber dashed `THERE IS NO FILE STORE`** was a stated absence and **it is now
   closed**. The store exists, the refusal sentence is deleted from all eleven
   catalogues, and the walk asserts the old words are gone by name.
2. **The solid red `Approval is blocked until every required document is checked`** is
   **superseded** — PO 2026-09-16, *"lets not make it mandetory"*. `blocks_approval` is a
   literal `False`. No gate was built. The walk asserts the sentence is not on screen.
3. **The right rail's plain prose** is the blueprint talking to its reader. None of it is
   on the screen, and the walk asserts each paragraph's absence by its own words.

---

## 4 · The known hazard, met head-on — `DEF-CUS-5872`

Six `service_request_documents` rows on the beta carry a `storage_ref` shaped
`sample-data://cr030/…` that resolves to no stored document at all. Every `size` is NULL
and **four of them read `verified`**.

**Every cell on this step asks `file_present`, never `attached`.** `has_real_file` is
exported from `service_request_documents` so there is ONE spelling of *is there a file*
rather than two that can disagree — `document_link`, `fetch_bytes`, `document_dict` and
`documents_tab` all ask it.

So a broken row draws `—` in FILE, `—` in UPLOADED BY and **`Nothing attached`** in STATE
**whatever its `verification_state` says**. The contradiction is not hidden: the row is
selected by the `Missing` chip. The walk opens a seeded request and asserts all of this
— the step renders without crashing, not one row claims a file, and not one offers to
open one.

⚠ **`attached` WAS NOT CHANGED, DELIBERATELY.** It drives the `verified`/`attached`
counts a live screen prints. Moving it is a maintenance fix with its own reproduce step
and blast radius, and it is named in `DEF-CUS-5872`'s prevention column.

---

## 5 · What the drawing draws and is NOT built, and why

| Drawn | Built | Why |
|---|---|---|
| *"Eight designed types, plus Anything else for whatever the applicant brought that helps."* under `Document type` (14 words) | **nothing** | RATIONALE — it describes what the dropdown already shows. B14 rule 33 puts rationale at **zero words on screen**. Shortening it to six words would still be the argument |
| *"Name and size are recorded, with who attached it and when."* under `File` (11 words) | **nothing** | same rule; and the table beside it already prints both facts |
| **`Attaching a file is not the same as verifying it.` Every attachment lands *Not checked* and stays there until somebody looks at it.** (24 words, bold) | **`Every attachment lands Not checked.`** (5 words) | This one is a FACT about what pressing the button will do, not a justification, so rule 33 caps it at six rather than banning it. The second clause — *stays there until somebody looks at it* — is rationale and is gone |
| an `Open` affordance on the FILE cell | **none** | p078 draws the file as TEXT. Opening, verifying and rejecting live on the request detail's Documents tab (PO 2026-09-19, *"we should have these detials in document tab"*). Also honest: the dev storage backend mints `file://` URLs a browser cannot follow, so a link here would be dead in every local walk and alive only in production |
| `Anything else` drawn as a ROW that is always present | a row only once somebody adds one | the table draws what the request HOLDS. `Anything else` is the ninth selectable TYPE, and `Add another document` is how a row of it arrives. A permanently drawn row would be a row with no id that nothing can attach to |
| the drawn figures — `1.2 MB`, `840 KB`, `3.1 MB`, `S. Ortiz`, `05/04/2026` | **not built to** | B14 rule 37 — a figure drawn in a wireframe is an ILLUSTRATION, never a fact to build to |
| `Save & exit` in the head | **`Save as draft`** | already recorded as Partial in `new-request-six-steps-measured.md`; it saves and does not exit. Not this lane's to settle |

---

## 6 · What this lane FOUND

### `DEF-CUS-5880` — reopening a saved draft shows an EMPTY wizard

The draft-load query calls `setDraft(loaded)` and **nothing ever calls `setForm`**, so
every box on steps 1 to 3 comes back blank while the server holds the values.

**Step 4 is not affected** — it reads the server, which is the whole reason the table was
built that way.

⚠ **THE DANGER IS NOT THE BLANK SCREEN.** Every step PATCHes the WHOLE payload, so a
clerk who retypes the name and address over the empty boxes sends blank email, phone and
Social Security number over stored values. `capturePayload`'s own comment predicted this
in as many words — *"The day rehydration is added, this field must be omitted from the
payload when it was not edited, rather than sent blank."* What stops it today is
`canCreateDraft` refusing an entirely empty form, which is an accident rather than a
guard.

**How it escaped:** every capture test mounts the wizard with no `?request=`, so the
draft-load query never runs and the empty form is the only form under test.

### `DEF-CUS-5881` — there is no door to reopen a draft at all

`serviceRequestCapturePath` builds the resume address and has **zero callers**. The
requests list and the request detail both offer `New request` and neither offers a way
back into a saved one.

**It must NOT be wired until `DEF-CUS-5880` is fixed.** A resume link onto a wizard that
loses its own values is worse than a shut one — which is hard-won law 2's mirror, a live
door onto a screen that does the wrong thing.

### A citation that pointed at a real, wrong defect

Two comments in this file cited **`DEF-CUS-5877`**, which does not exist. **5877 is taken
by `DEF-GOV-5877`**, about background jobs — so every id-existence check passes over it
and a reader is sent somewhere real and wrong. That is `DEF-2804`'s shape. Both now cite
`DEF-CUS-5880`.

---

## 7 · Three faults in the PROOF, found by running it

Worth as much as the screen work, because each is hard-won law 7's shape.

1. **A cell printed the literal word `undefined` to a clerk.** The test was
   `doc.uploaded_by_name !== null`, and **that is TRUE when the key is ABSENT**. It
   appeared the first time the walk ran against a server that had not picked the field up
   yet. **Typescript cannot catch it** — the field is typed `string | null` and a running
   server is free to be older than its own type. Three cells had the same shape; all
   three now collapse missing and null before asking.
2. **`p.check()` timed out for thirty seconds against a working control.**
   `CheckboxField` renders its real `<input>` as `peer sr-only` with no size, so
   playwright's actionability wait can never be satisfied. The failure had nothing to do
   with the product. A clerk clicks the words, and the walk now clicks the label.
3. **The table was asserted on a request created thirty seconds earlier**, which holds
   nothing and therefore draws no table. That check **could only ever have passed against
   a header over five empty columns** — a shape the drawing does not draw. It now asserts
   the honest empty state there, and the table after the first attach.

### And one check that was measuring something no rule says

The step's prose budget **summed every paragraph** and demanded six words in total. Rule
33 caps each **FACT** at six words; rule 32 allows **one sentence per SECTION** plus a
stated absence. The summed version went red on two perfectly lawful four-word sentences
and — far worse — **would have gone GREEN on a single six-word sentence of pure
RATIONALE**, which is the only thing rule 33 actually bans. It now caps each sentence
individually, counts stated absences separately because rule 32 names them, and holds the
step to at most ONE sentence of its own prose. Against the tip build it reports a 25-word
sentence, so it can fail.

---

## 8 · The beta, counted before and after

| | Before | After |
|---|---|---|
| service requests | 8 (+1 orphan draft from an interrupted run) | **8** |
| `service_request_documents` | 6 | **6** |
| `stored_documents` | 184 | **186** |

Six tagged drafts were purged by their tag and nothing else — the five this lane's runs
saved, plus the orphan the interrupted run before it left behind.

⚠ **THE TWO STORED OBJECTS CANNOT BE PURGED, AND THAT IS THE PRODUCT WORKING.**
`stored_documents` is write-once under a seven-year object lock (`BR-SHL-031`,
`NFR-35`). Two 50-byte objects remain, named by nothing and reachable from nothing.
Stated here rather than left to be discovered.
