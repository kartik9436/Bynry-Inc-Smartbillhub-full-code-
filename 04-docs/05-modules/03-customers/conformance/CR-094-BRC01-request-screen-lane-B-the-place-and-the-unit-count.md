# The request's place, named — and what the applicant says is on the property

**`CR-094-BRC01` wave 1, lane B · 2026-09-15 · started at `1b64ad92`,
re-derived twice and landed on `829ac527` as commit `e4092d3e`**
Defect work under `CR-094-BRC01` (`13-change-process.md` §1 — making the product
match a signed drawing is a defect, not a change).
**This lane wrote no screen.** Everything below is the server and its record.

⚠ **THE PUSH-TIME RE-DERIVATION FOUND SIX COLLISIONS WITH TWO SIBLING LANES, AND
ONE OF THEM WOULD HAVE BROKEN EVERY TEST IN THE PROCESS** — see §10. Read that
section before the rest if you are here because something collided.

---

## 0 · The pages I read, AS IMAGES, and at what scale

PO instruction of this date, verbatim: *"I want you to use images only to create
screens - do not use text or content ot create product screens"* — and B14 rule
42: extracted text is an index, never the specification.

| page | what it is | scale | file |
|---|---|---|---|
| **p077** | capture step 3, *Addresses* — the five drawn address boxes, `The property` with `How many units are on this property? *`, the billing-address box, and the `What the register matched` table | **2** | `scratchpad/acct/p077.png` |
| **p082** | the register's Requests tab and the top of the request's own screen — the head, the meta line, the full address line, and `WHAT THEY ASKED FOR` with `Units on the property · 6` | **2** | `scratchpad/acct/p082.png` |
| **p083** | the rest of the request's screen — `THE ADDRESS THEY GAVE`, the fees block, the history table, and the Approve modal | **2** | `scratchpad/acct/p083.png` |
| **p083**, the `THE ADDRESS THEY GAVE` block alone | re-rendered because the three row labels and the two match values were not legible at scale 2 | **6**, cropped to `(1850,380)-(4350,1200)` | `scratchpad/laneB/p083_address_block_s6.png` |

`10-scripts/pdf/pdf_render.py` renders a whole page; it has no crop, and the
Read tool downscales a 7,344px sheet back to illegibility. The crop was made
with a six-line script using the same `pypdfium2` + zlib technique
(`scratchpad/laneB/crop.py`), which is why a scale-6 read of one block was
possible at all. **Say so rather than claiming a scale nobody can reproduce.**

**What the scale-6 read settled**, and it is the whole of commitment 3:

```
THE ADDRESS THEY GAVE
  As given            212 Balcones Drive, Unit 3, Austin TX 78704
  Matched premises                                PR-0731 · exact
  Matched unit                                  U-001884 · exact

  What they typed is kept beside what we matched, never replaced by it.
  The resolver is evidence; if the two ever disagree, the clerk can see both.
```

Three rows. The address is ONE line carrying street, unit, town, state and
postcode. The two matches are NAMED and each carries a word after it.

---

## 1 · What the ruling was when I started, and what it was an hour later

**I built three columns the Product Owner then ruled out, before anything was
pushed.** It is written here first because it is the most useful thing in the
file for the next lane.

**Started from** the decision-log row of 2026-09-15: *"with the address shown in
full (city, state and ZIP do not exist and are to be built)"*. Built
`address_city_as_given`, `address_state_as_given`,
`address_postal_code_as_given` on `service_requests` — model, a migration,
`CAPTURE_FIELDS`, a widened post-submission refusal, and a **fifth `G85` home
entry field-scoped to exactly those three**.

**Then the PO ruled**, verbatim: ***"if we have unit or street address then we
should take it from premises/Unit - it means its a search and if not foudn them
alow user to add them"***.

All three came out. The migration was deleted and rewritten. **Nothing carrying
them was ever pushed**, so there is no revert to chase.

**Why the first reading was wrong, stated so it is not re-argued:** the ruling is
`CLAUDE.md` hard rule 8 / `BR-MET-1161` applied to this screen rather than a new
rule. Capture is a SEARCH of the premises register; the town, the state and the
postcode are the matched premises' own facts and are read by walking to it, the
way `DEF-CUS-3653` fixed the account header when `addresses.kind='service'` was
retired. Where the search finds nothing, a premises is added and the facts are
still its.

**Why the first reading was defensible, which is why the near-miss is written
into four files:** a service request records what a stranger said at a counter
**before any premises exists**, which is the shape of hard rule 8's own second
exception — `interruptions.location_text`, *"what a stranger typed — a report,
not a record"* — and p077 says the same in its own words: *"The address is the
APPLICANT'S, not a record"*, *"an applicant's address is not a premises yet"*.
A good argument, and still the wrong answer. The next lane reading five drawn
boxes will make it again, so `models.py`, the migration, `CAPTURE_FIELDS` and
`g85_one_address_home.py` each carry a ⛔ paragraph naming the ruling.

---

## 2 · THE PAYLOAD, PUBLISHED — what wave 2's screen builds against

`GET /service-requests/{id}` · `service_request_reads.detail`.
**Additive only. No key was renamed and none was removed.**

### `header` — gains three

```jsonc
"header": {
  "request_no": "SR-26-0001",
  "state": "more_info",
  "classification": "not_yet_classified",
  "applicant": "Osei, Grace",
  "address_as_given": "3450 Oak Ridge Dr",          // unchanged
  "address_unit_as_given": "3450 Oak Ridge Dr · Unit 1",   // NEW
  "premise_locality": {                                    // NEW
    "city": "Silver Creek", "state": "TX", "postal_code": "78611"
  },
  "lookup_found": "customers.serviceRequest.lookup.servedAndVacant"
}
```

The head is drawn ABOVE the tabs and draws the address line in full (p082), so
it must not have to read a tab to draw itself.

### `location_and_services` — gains six

```jsonc
"location_and_services": {
  "address_as_given": "3450 Oak Ridge Dr",
  "address_unit_as_given": "3450 Oak Ridge Dr · Unit 1",
  "units_on_property": null,                    // NEW — integer | null
  "billing_address_same": true,                 // already served since W4
  "billing_address_as_given": null,             // already served since W4
  "resolved_premises_id": "01a0a444-5ad2-7e88-be8a-bdb8aa86c05e",
  "resolved_unit_id": "01a0a444-5ada-7109-974b-d4c7143b9547",
  "resolved_premises_no": "P-00052",            // NEW  ← DRAW THIS
  "resolved_unit_no": "SCW-U-207",              // NEW  ← DRAW THIS
  "resolved_premise_address": "3450 Oak Ridge Dr",  // NEW — the fallback
  "premise_locality": {                             // NEW
    "city": "Silver Creek", "state": "TX", "postal_code": "78611"
  },
  "resolved_match": "exact_reference",          // NEW — the word after the number
  "resolution_kind": "served_vacant",
  "lookup_found": "customers.serviceRequest.lookup.servedAndVacant"
}
```

**That is a real request on the demo tenant**, read out of PostgreSQL on
2026-09-15: `SR-26-0001` on `brazosbend`, the one the measurement caught printing
`RESOLVED TO 01a0a444-5ad2-7e88-be8a-bdb8aa86c05e` to a clerk. `units_on_property`
is `null` there because nothing has ever written one; setting it to `6` inside a
**rolled-back** transaction served `"units_on_property": 6` and changed nothing on
the shared tenant.

**Six rules for the lane that draws this:**

1. **Draw the NUMBERS, not the ids** (`DEF-CUS-5386`, B14 rule 31 — PO, *"no
   Databse ID on screen - that is a rule"*). The ids stay in the payload for
   links and for `title=`, which is `DEF-2716`'s proved fix.
2. **Either number can be `null` while its id is not.** `premises.premise_no` and
   `units.unit_no` are both nullable. Fall back to `resolved_premise_address`,
   then to a stated absence — **never to the id**, which is the defect coming
   straight back.
3. **`premise_locality` is the PREMISES', not the applicant's.** The name says so
   on purpose. Anything you label as what the applicant gave must come from
   `address_as_given` / `address_unit_as_given`.
4. **Compose the address line on the screen.** The server never composes it: the
   blueprint punctuates the same line two ways on two frames — `Austin TX 78704`
   on p083, `Austin, TX 78704` on p082 — so the punctuation is an illustration
   (B14 rule 37) and choosing between two drawings is not a server's job.
5. **`units_on_property: null` renders as *not supplied*, never as `0`.** Zero is
   a real answer (vacant land) and the two must not look alike.
6. **`resolved_match` goes through the catalogue**, the way `resolution_kind`
   already does. It is a code, not a word to print.

⚠ **The fixture in `ServiceRequestDetailPage.test.tsx` resolves to NOTHING**, so
it cannot catch `DEF-CUS-5386` at all — the raw-id branch never renders. A wave-2
case that fixes the screen needs a **resolved** fixture, ids AND numbers set, or
the assertion it is built on cannot fail. The file carries that warning inline.

---

## 3 · Before and after, per commitment

| # | the commitment | before | after |
|---|---|---|---|
| 1 | **Units on the property** — *"we need to build this"* | no column; the drawing's own annotation says the number *"lives only in whatever the clerk typed into the notes, which no screen and no rule can read"* | `service_requests.units_on_property`, nullable integer, accepted by the capture endpoint, served on the location payload |
| 2 | **City, state and ZIP** | no columns | ⛔ **SUPERSEDED MID-BUILD.** Not columns. `premise_locality` is walked to the matched premises and served on both the head and the tab |
| 3 | **The matched premises and unit, named** (`DEF-CUS-5386`) | `resolved_premises_id` served and printed raw: `01a0a444-5ad2-7e88-be8a-bdb8aa86c05e` | `resolved_premises_no P-00052`, `resolved_unit_no SCW-U-207`, `resolved_premise_address`, `resolved_match exact_reference`, the ids still there. **SERVER HALF ONLY — the screen is wave 2's and the defect stays OPEN** |
| 4 | **The billing address, served** | **already served since W4**, and the capture step has collected it since REQ-03.3 | **nothing changed.** A test now holds both fields still so a later tidy-up cannot drop them |

**Commitment 4 needed no code and that is the answer, checked rather than
assumed:** `location_tab` has carried `billing_address_same` and
`billing_address_as_given` since W4. The PO's *"we have to show service address
and also allow to take billing address"* is unmet **on the screen**, which draws
neither, and the screen is wave 2's.

---

## 4 · Why the unit count is not an address, and does not breach hard rule 8

The brief asked for this in writing, and after the reversal it applies to the one
column that survived.

* Hard rule 8 / `BR-MET-1161` governs **where a place's address lives**: on
  `premises`, once, with everything else walking to it.
* `units_on_property` is **not an address**. It is a count, and it is the
  APPLICANT'S count — p077 helps the field with *"What the applicant says is
  there"*. The drawing's own match table puts it beside the register's figure as
  two facts that may disagree: `Units on the property · 6` against `6 units on
  PR-0731`, confidence `Agrees`.
* Nothing reads it as the truth about the building. A premises' real unit count
  is metering's and is reached by walking, as it always was.
* **`G85` was checked before the push and is green at four homes.** It was also
  proved RED on this tree with a `city` added to `ServiceRequest`, through
  `module.run()` — the line `run_gates.py:2598` actually executes, not
  `__main__` (`DEF-GOV-3733`).

---

## 5 · The blind spot I found, and did not close — `DEF-CUS-5400`

**`G85` matches address columns BY EXACT NAME** against a closed list of fifteen.
`address_city_as_given` is not one of them, so **the gate would have passed my
fourth address home silently**. That is hard-won law 7's fifth shape — a check
reporting zero over a scope it excludes, and the hardest to see because the check
is not lying.

Three live columns are in that blind spot today, all lawful:
`service_requests.address_as_given`, `service_requests.billing_address_as_given`,
`portal.PortalApplicationDraft.address_as_given`.

**What I did:** the gate now prints what it did not look at beside what it did —

```
G85 PASS: 4 ruled homes and no unruled one — … ; NOT SEEN: 3 `*_as_given`
address columns this name-matching gate cannot reach (DEF-CUS-5400)
```

**What I did not do, and why:** the real fix is a SUFFIX match instead of an
exact-name set, so `address_city_as_given`, `service_address_line` and
`mailing_city` are all seen and then ruled on. Widening the alphabet turns every
currently-invisible column into a FAIL that has to be ruled on first — which is
the right conversation and is not a wave-1 lane's to start on a gate three
modules depend on.

---

## 6 · Proof

### Every guard proved RED first, on this tree, and quoted

| # | guard | the sabotage | the failure, verbatim |
|---|---|---|---|
| 1 | the premises and unit NUMBERS are served | `resolved_premises_no` forced to `None` | `E AssertionError: assert None == 'P-00101'` |
| 2 | the locality is WALKED | `premises_locality(…)` replaced with `None` | `E AssertionError: assert None == {'city': 'Austin', 'state': 'TX', 'postal_code': '78704'}` |
| 3 | the unit count is ACCEPTED | `"units_on_property"` removed from `CAPTURE_FIELDS` | `E core.errors.ValidationError: VAL-005 (customers.serviceRequest.fieldNotAccepted)` |
| 4 | a bad count is REFUSED | `_clean_unit_count` bypassed | `E ValueError: invalid literal for int() with base 10: 'six'` |
| 5 | no address part may return | `address_city_as_given` added back to the model | `E AssertionError: service_requests.address_city_as_given would be a fourth address home…` |
| 6 | `NFR-5` — no maximum | a `count > 500` cap added | `E core.errors.ValidationError: VAL-005 (customers.plan.wholeNumber)` |
| 7 | the address freezes at submission | the `BR-CUS-070` refusal short-circuited | `E Failed: DID NOT RAISE BizError` |
| 8 | both addresses reach the screen | `billing_address_as_given` forced to `None` | `E AssertionError: assert None == 'PO Box 41, Austin TX 78767'` |
| 9 | **`G85` still bites**, through `module.run()` | a bare `city` on `ServiceRequest` | `G85 FAIL: apps/customers/models.py::ServiceRequest declares ['city']. An address is stored on 'premises' (BR-MET-1161…` |

Harness: `scratchpad/laneB/redproof.sh`. Every file was restored and
`git diff --stat` confirmed only the intended hunks remained.

⚠ **AND ONE RED I DID NOT PLAN, WHICH IS THE ONE WORTH READING.** The first draft
of the `premise_no is null` case nulled the numbers **before** resolving, so the
resolver found nothing and the case failed `assert None == '77 Cedar Court'` —
it was asserting over an unmatched request and proving nothing about the
fallback. The order is now the test: resolve, THEN take the numbers away. The
comment in the case says so, because the next reader will want to move that line.

### Green

| what | result |
|---|---|
| `test_cr094_request_place_and_units.py` | **11 passed** |
| `test_cr031_service_request.py` + `..._api.py` + mine | **106 passed, 1 skipped, 2 failed** — both failures dated below and neither mine |
| migration applied to live PostgreSQL and **read back** | `\d service_requests` → `units_on_property \| integer \|  \|  \|` |
| the read, against the demo tenant's real rows | `SR-26-0001` → `P-00052` · `SCW-U-207` · Silver Creek, TX 78611 |
| `tsc --noEmit` (the repo's own 5.5.4, not a fetched one) | **exit 0** — and proved able to fail first: my type additions produced four `TS2739`/`TS2740` errors in two fixtures before I updated them |
| `vitest run` on the two request screens' test files | **89 passed** |
| `G85` through `module.run()` | PASS, 4 homes, 3 not seen |

⚠ **`tail` ATE AN EXIT CODE AND THE NUMBER LOOKED FINE.** The first `tsc` run
ended `… \| tail -15; echo "tsc exit: $?"` and printed `tsc exit: 0` **over four
compiler errors** — `$?` was `tail`'s. The real run redirects to a file and reads
`$?` off `tsc` itself. A check whose output cannot distinguish pass from fail is
worse than no check, and this one was mine.

---

## 7 · Reds I did not cause, DATED

Law 7 habit 1, and *"was it red before I started"* is a claim about history, so
it was checked rather than asserted.

| red | dated how | verdict |
|---|---|---|
| `test_cr031_service_request.py::test_the_list_is_oldest_first_and_segments_by_state` and `::test_us_cus_025_tc2_the_list_is_oldest_first` | **Re-run at the tip with every lane-B change removed** — the three touched files replaced by their `1b64ad92` versions and the two cases run: **2 failed**, same `AssertionError` at line 1427. Then restored. | **NOT MINE.** `BR-CUS-1046` reversed the list order to newest-first on 2026-09-12 and the tests still assert oldest-first, quoting the superseded on-screen sentence in their own docstrings. The read model's current text arrived in `2db4d169` (2026-09-13); the test file last moved `d6d31c46` (2026-09-04). ⚠ **I FILED IT AND THEN UNFILED IT.** It was not in the register when I looked, so I filed it; by push time a sibling lane had pushed **`DEF-CUS-5393`**, the same finding in almost the same words, and taken the number I had. **Their row stands and mine was dropped** — two records of one thing is worse than one, and the register is not the place to prove who saw it first. |
| `test_be11_openapi.py::test_be11_tc05_the_committed_snapshot_matches_what_the_code_exports` | Exported the schema and diffed: **46 lines, one path, `/api/{tenant}/billing/print-sets/bills`**, and **zero** occurrences of `service-request` in the diff. `git log -S "print-sets/bills"` → `07d1fb37`, 2026-09-15, *"Build Print bills as drawn… (CR-101-BRC03, lane J)"*. | **NOT MINE.** Already carried as `DEF-GOV-5342` (and `DEF-GOV-4639` before it). **Deliberately NOT regenerated:** `manage.py export_openapi` would put another lane's contract change inside this lane's commit, which is law 11's fifth mechanism — publishing somebody else's work. |

The `kombu.exceptions.OperationalError: Error 111 connecting to localhost:6379`
lines in every run are a queued job that cannot dispatch with no broker running.
They are LOGGED, not raised, and no case fails on them.

---

## 8 · What I did not build, and why

* **The screen.** `ServiceRequestDetailPage.tsx` still renders
  `loc.resolved_premises_id`, so a clerk still sees a UUID. **`DEF-CUS-5386`
  stays OPEN** and is wave 2's. The two `.tsx` files I touched are the TYPE and
  two fixtures, to keep `tsc` compiling.
* **Capture step 3's unit-count box.** The column and the endpoint take it; no
  screen sends it yet. Part of `DEF-CUS-5385`, which also covers the drawn match
  table, and belongs with whoever rebuilds that step — now under the new ruling,
  as a premises SEARCH rather than five boxes.
* **The five-box address form.** Ruled out mid-build. What replaces it is a
  premises search with *add one when nothing is found*, which is a screen and a
  lookup endpoint, and is nobody's yet.
* **Searching the request list by town or postcode.** `list_queryset` searches
  request number, name, address-as-given, phone and email. Adding the premises'
  locality is a join and a separate decision; the drawn placeholder does not ask
  for it.
* **`G85`'s suffix match** — `DEF-CUS-5400`, reasoning in §5.
* **The two stale list-ordering tests** — `DEF-CUS-5393`, a sibling lane's row
  and not mine (see §7). A shared test file with two sibling lanes live in the
  same wave, and the fix is a judgment about a ruling, not a typo. It deserves
  its own commit.
* **No locale key was minted.** `_clean_unit_count` reuses
  `customers.plan.wholeNumber` — *"This must be a whole number."* — which is in
  this module, carries no parameters, and is already translated in all eleven
  catalogues in each language's own words. One new backend refusal obliges eleven
  frontend files from a backend lane while two sibling lanes are live in them;
  that is the `CR-023` P3/P4 precedent of 2026-08-21 and the collision law 11
  exists to prevent. **The reuse is reported here rather than hidden.**

---

## 9 · One correction to the wave brief, made in the repo and not only in a reply

The brief said the request already stores `match_tier` and `match_basis` for the
address match, and that the lane should *"serve the numbers and the tier"*.

**It does not.** `service_requests.match_tier` and `match_basis` are
`BR-CUS-089`'s **CUSTOMER** match — *is this applicant the Sarah Miller we
already bill* — with `strong | probable | weak` and a `may_move_money` gate hung
off them. The ADDRESS match's evidence is `resolution_kind` and `lookup_found`,
and it had **no** confidence value at all.

Reading one for the other is `DEF-2804`'s shape — a real field read for a
different real field — on the screen a clerk decides an application from. Serving
`match_tier` beside the premises number would have printed a customer-identity
tier under a heading about a building.

`resolved_match` is what was built instead: derived, not stored, and a statement
about the mechanism rather than an invented score — `seams.unit_id_for_reference`
resolves by **exact reference only** (`BR-CUS-047`), so a match this product made
IS an exact-reference match. A fuzzy matcher would add a second value rather than
change what this one means. Both the constant and the decision log carry it.

---

## 10 · The push-time re-derivation, and the four collisions it found

**Everything in §6 was proved at `1b64ad92`. By the time this lane pushed, the
tip had moved TWICE** — to `b0f3f67e` (lane C, in eight of my files) and then to
`829ac527` (lane A, in three more) — **and the whole re-derivation had to be
done twice.** Law 11's re-derivation is the only reason any of it was noticed;
every other check in that law passes on all of these.

⚠ **THE SECOND ROUND COST EVERY NUMBER AGAIN.** `0048` was taken by lane A's
`0048_cr094_request_raises_the_job`, and `5395`/`5396` had both gone to siblings
in the forty minutes between the two rounds. **The final, landed values are
`customers/0049`, `DEF-CUS-5400` and `DEF-GOV-5401`** — the ids named in the
table below are what they COLLIDED with, and the final landing point is here so
a reader does not have to reconcile the two.

| what collided | how | what was done |
|---|---|---|
| **The migration number** | Lane C pushed `customers/0047_cr094_service_request_applicant_messages.py` and mine was also `0047`. **Two leaf nodes in the migration graph — Django then refuses EVERY TEST IN THE PROCESS** with an error naming neither lane. Reproduced deliberately before fixing it: `CommandError: Conflicting migrations detected; multiple leaf nodes in the migration graph: (0047_br_cus_1055_units_on_property, 0048_br_cus_1055_units_on_property in customers)` | Mine ended as **`0049`** and depends on lane A's `0048`, so the graph keeps ONE leaf. The dev database was unwound properly — `migrate customers 0046` reversed my old `0047` (dropping the column), then both applied in order — rather than by editing `django_migrations` |
| **`DEF-CUS-5391`** | Taken by a sibling for the acknowledgement defect | mine renumbered to **`DEF-CUS-5400`** and every citation moved with it (the gate, the test's trace header, this file) |
| **`DEF-GOV-5392`** | Taken as `DEF-NOT-5392` — a different id, the SAME NUMBER, which `G17` fails by name | mine renumbered to **`DEF-GOV-5401`** |
| **`DEF-CUS-5393`** | Taken by a sibling **for the same finding** — the two stale list-ordering cases, in almost the same words | **my row was dropped.** Theirs stands |

`BR-CUS-1055` was re-checked against the tip and is still free; lane C took
`BR-CUS-1070` and `BR-CUS-1075`.

**How each file came back:** the three Python files were re-derived by writing
the TIP's bytes and re-applying this lane's own hunks as a patch (all three
applied cleanly, one with a one-line offset). The three markdown registers were
rebuilt as *the tip's file plus my one row*, and the defect register's prefix was
proved **byte-identical to the tip** before it was installed — a register whose
first N bytes match the tip cannot have reverted anybody.

⚠ **THE ALLOCATOR SAID `TAKEN` THREE TIMES AND THAT IS THE TOOL WORKING, NOT
FAILING.** `allocate.py defect --verify` cannot reserve and does not claim to; it
removes the stale read, and it caught all three at the only moment the answer can
be final. Running it *before* writing the rows would have found nothing, because
the sibling had not pushed yet.
