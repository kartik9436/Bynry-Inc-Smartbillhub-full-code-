# J31 — Guest reports a burst main and tracks it to *crew on site* (`RP-26-0412`, a reporter who is not a customer, and a smell of gas that creates nothing)

---
id: J31
tier: 2
rules: [BR-CWP-022, BR-CWP-023, BR-CWP-024, BR-CWP-025, BR-CWP-026, BR-CWP-027, BR-CWP-028, BR-CWP-076, BR-CWP-078, BR-CWP-084, BR-CWP-093, BR-CWP-012]
stories: [US-CWP-001, US-CWP-002, US-CWP-007, US-CWP-008, US-CWP-009, US-CWP-010, US-CWP-011, US-CWP-063, US-CWP-069]
# Wiring: every story above cites `J31` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J31.spec.ts` exists. Release 1.
# ⚠ `US-CWP-011` (planned work, CWP-058) is BLOCKED on OQ-249 and this journey
# stops at its boundary in step 9. `CWP-005` (public status page) is NOT in
# scope at all (CR-068 R9) and is not a step here.
---

**Intent.** A passer-by standing over water coming up through the pavement tells the
utility, with no account and no exact address, and gets a **reference** they can look up
tomorrow without signing in. Behind the form the product gains a record it has never held —
an **interruption** — owned by `metering`, with the one piece of new thinking in the whole
portal blueprint: an **affected area** (*Elm St, 1400–1500*) that resolves to a set of
premises. The request reaches a clerk's worklist carrying channel `customer_portal`, **the
first rows in the product ever to carry that value**.

**Three assertions the flow document names, and this journey proves each:** the reporter
is **not** a customer and it still works · the **sixty-first** submission in a minute is
refused · **`gas_smell` returns a phone number and creates nothing**.

**Upstream leaves (handoff in).** Tenant `pine-hill` live, `outage_reporting_enabled =
true`, emergency number `(512) 555-0100`. Premises `1408 Elm St` (units A, B, Common) and
`1412 Elm St` on the stretch; `22 Palm Ct` outside it. Tenant `oak-ridge` with a street
also called *Elm St*. `service_request.channel` has the value `customer_portal` in its
enum and **no row has ever carried it**.

**This journey leaves (handoff out).** ONE `interruption` row (metering) — `kind =
leak_or_burst`, `location_text = "1408 Elm St, Austin TX 78702"`, `premises_id` NULL
until a clerk resolves it, `affected_area = {street: "Elm St", from: 1400, to: 1500}`,
`status` walked `looking_into_it → crew_on_site → resolved`, `reporter_name`,
`reporter_phone`. ONE `service_request` row, reference `RP-26-0412`, channel
`customer_portal`, with one customer-visible note and one **internal** note. ONE optional
photo in the existing document store. **Zero** changes to any `account`, `customer` or
money table.

**Fixture.** Reporter **D. Okafor**, `(512) 555-7730`, **not a customer**. Location
`1408 Elm St, Austin TX 78702` (free text). Notes *"Water coming up through the pavement
outside number 1412, been going since about seven…"*. Reference issued `RP-26-0412` at
**2 Sep 2026, 9:52am**. Wrong track pairs `RP-26-0413`…`0417` + `78702`. Internal note
*"route to Tuesday crew, low priority"* (must never appear). Second interruption *low
pressure, Cedar Row, since 8:20am, no ETA, looking_into_it*. Screens `CWP-006` →
`CWP-007` → `CWP-012` (and `CWP-051` for the signed-in half of `US-CWP-063`).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (record · worklist · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | Guest opens `/pine-hill` → *Report a problem* (`CWP-006`) | `RadioList` × 6: *No water at all · We treat this as urgent* · *A leak or a burst* · *Low pressure* · *Smell of gas · Ring us — do not use this form* · *A missed collection* · *A damaged meter or cover*. Rail `Panel.Emergency` *Is anyone in danger?* with `(512) 555-0100` bold. Subtitle *You do not need an account.* | No session, no account lookup. *Check my area* is **absent** from the front page (`R9`). With `outage_reporting_enabled = false` the card is absent **and** `POST /public/reports` refuses | BR-CWP-027 · BR-CWP-093 |
| 2 | **negative · routing, not a disclaimer** — selects *Smell of gas* | The form returns **`(512) 555-0100`** and **creates nothing**: no `service_request` row, no `interruption` row, no document, no audit row of a submission | Assert all four counts unchanged. A form that quietly accepts *smell of gas* and queues it behind a missed collection is worse than no form | BR-CWP-027 · `US-CWP-007` TC-3 |
| 3 | Selects *A leak or a burst*, types the free-text location, the notes, name and phone; attaches a photo; *Send this report ✓* | `RP-26-0412` issued. `interruption.kind = leak_or_burst`, `location_text` stored **byte for byte**, `premises_id` **NULL** — the address is free text **resolved later by a clerk**; demanding an exact premises match would refuse the person standing over the burst. `service_request.channel = customer_portal` | The photo went through the **existing** document store — its allow-list and size cap (the malware scan before acceptance is SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload), `DEF-SHL-6347`). A report with **no phone** is refused (*we ring you only if we need to* requires a way to ring). A second report from the same street is **accepted** and the screen says the street is already reported — *we would rather hear twice than not at all* | BR-CWP-027 · BR-CWP-076 |
| 4 | `CWP-007` — report sent | Kicker **SENT**, *Thank you — that is with us*, `KVList` Reference `RP-26-0412` / Reported *2 Sep 2026, 9:52am* / Where *Near 1412 Elm St* / What *A leak or a burst*. Rail `ChecklistTimeline` × 4: *You told us · 9:52am* done, **We look at it** current, *A crew is sent if needed*, *We close it off*. Buttons *✉ Text me the reference* · *Check my area* | *Text me the reference* sends **through the existing outbound queue** to the phone given on the form — never inline. The closing sentence *Two people reporting the same burst is not a problem* is present. The reference is the **entire record** of the interaction for a guest | BR-CWP-028 |
| 5 | A clerk (Priya Menon) sets the affected area *Elm St, 1400–1500* and moves the interruption to `crew_on_site`, `expected_back_on` ≈ 2pm; adds the **internal** note and one customer-visible note | The affected area resolves to `1408 Elm St · A`, `· B`, `· Common` and `1412 Elm St` — **and to nobody else**: `22 Palm Ct` is not in the set. `CWP-007`'s timeline moves **without anyone editing the customer's page** | An affected area naming a street with no premises resolves to an **empty set and the record is still valid** — an interruption can exist before we know who it touches. Resolving an already-`resolved` interruption is refused, not recorded as a second event. `expected_back_on` in the past with status still `crew_on_site` shows **open** — the clock does not close a record, a crew does | `US-CWP-008` TC-2…TC-6 · BR-CWP-012 |
| 6 | Guest, next day, signed out, `CWP-012` — `RP-26-0412` + `78702`, *Look it up →* | *"A leak or a burst, near 1412 Elm St · Crew on site"* with the dates. The response body contains **no customer name, no balance, no other reference** — asserted on the body, not the rendered page | The direct URL from the confirmation is trusted for **that session only**; a fresh visit requires the postcode or the phone — a reference alone is guessable. `SR-26-0056` + `(512) 555-4218` (the phone given) returns a move-out's progress the same way; `PAY-26-08841` + `78702` returns a payment's status and date **and not its amount** | BR-CWP-024 · BR-CWP-025 |
| 7 | **negative · the hidden half** — the same page after the clerk's internal note | The note *"route to Tuesday crew, low priority"* is **absent**. Only transitions and notes flagged `customer_visible` appear. Assert the response body does not contain the string | The same read serves the signed-in `CWP-051` (`US-CWP-063`) — one customer-safe history, two surfaces. `account_note.customer_visible` is the boundary, and it has been inert until now | BR-CWP-078 |
| 8 | **negative · the guard** — the 61st `POST /public/reports` in one minute; six wrong track pairs from `198.51.100.10` | The 61st is refused in five or six words naming no code. The sixth wrong track pair reads *"locked for fifteen minutes"*; the lock is **independent** of the quick-pay lock; `203.0.113.7` is not locked | The lockout is a cache entry keyed tenant + form + address — **not a table**. 60 in a minute are all accepted | BR-CWP-022 · BR-CWP-023 |
| 9 | **boundary · `OQ-249`** — planned work (`US-CWP-011`) | Two planned works seeded **directly** (*Water main replacement · Elm St, 1400–1500 · 4–5 Sep · Planned*; *Meter exchange programme · Palm Ct · week of 15 Sep · Scheduled*) render on `CWP-058` and appear in `CWP-053` for `1408 Elm St · A` **and not for `22 Palm Ct`**. **The planned-work write path raises `NotImplementedError("OQ-249")`** — the id in the code. With no planned work the page and its link are **absent**, not an empty table | `planned_outage` gets **no migration** until `OQ-249` (the field-work module's scope, older than this module) is ruled — its affected-premises rule is that module's shape. The notification event exists and is refused by name. A portal row is a record that a message exists, never proof it arrived | BR-CWP-093 · BR-CWP-084 · `OQ-249` |
| 10 | **tenant isolation** | `RP-26-0412` + `78702` under `/oak-ridge` → **not found**. A report submitted on `/oak-ridge` lands under Oak Ridge only and appears on **no** Pine Hill worklist. Pine Hill's affected area *Elm St, 1400–1500* resolves within **Pine Hill's** premises only, though Oak Ridge has an Elm St too | RLS `FORCE` on `interruption` and `service_request`; `app.tenant_id` set from the path before any read | hard rule 1 · `US-CWP-008` TC-5 |
| 11 | **INVARIANCE — a public form creates work and never changes an account** | From step 1 to step 10 the form wrote an `interruption`, a `service_request`, a document and queue rows — and **no row of `account`, `customer`, `customer_contact`, `payment` or `invoice` changed**. Assert byte-identical snapshots of those tables before and after | The reporter never became a customer; no credential was created; `premises_id` was set by a **clerk**, not by the form. Every clerk action on the interruption is audited | BR-CWP-026 · hard rule 7 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | Planned work reaching `CWP-058`/`CWP-053` from a **real** work record | `OQ-249` — the field-work module's scope. Step 9 seeds directly and asserts the write path raises |
| b | The public status page `CWP-005` | Not in scope — `CR-068` `R9`: *reporting ships, the status page waits until somebody owns keeping it current out of hours*. Do not put it in a build plan |
| c | The text-message reference actually arriving | The SMS channel is Twilio, `COMING_SOON · v1.1` (`BR-INT-001`). The queue row is asserted; delivery is not |

---

## ⚠ AS BUILT — 2026-09-04, CR-068 wave B (`2.139.0`)

**The journey above was written from the documents; this is what the code does.**
Where the two disagree the CODE wins and the difference is stamped here rather
than quietly reconciled (`10-execution-plan.md` §0's rule). Nine differences, and
`10-scripts/render-checks/cr068-b-report-and-track.mjs` is the proof of the half
that IS built — thirty-two assertions against a running product.

| Step | The journey says | What the code does |
|---|---|---|
| header | *"`service_request.channel` has the value `customer_portal` in its enum"* | It is **free text**, not an enum — `customers/models.py`'s own comment says why, and there is no migration. The value is a constant in one place (`portal/seams/customers_seam.CHANNEL_CUSTOMER_PORTAL`) so the writer and every count spell it once |
| 3 | *"attaches a photo … through the existing document store — its allow-list, size cap and malware scan"* (the scan clause is SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload)) | **NOT BUILT, and asked rather than assumed.** Consumer upload is a signed deferral (PO 2026-08-08, `DF-4`; `CR-068` §2b). The picker renders HELD with its reason, there is **no file input at all**, and the guest edge REFUSES a payload naming one rather than dropping it — a screen that says *attached* over nothing is worse than one that says no. The re-sign is a review-ledger row of 2026-09-04, in plain English with its figure |
| 4 | *"Buttons ✉ Text me the reference · Check my area"* | *Text me the reference* is **HELD** — SMS is Twilio in W8 (`10-execution-plan.md` §0 row 23), and a live button over a queue nothing consumes is hard-won law 2. *Check my area* is **absent**: `CWP-005` is not in scope at all (`R9`) |
| 4 | The reference on `CWP-007` is the request's | It is the **INTERRUPTION's**, from a NEW thirtieth number series `interruption_report` (`RP-{YY}-{0000}`). The clerk's `SR-` number is a clerk's vocabulary and is **never served to a guest** — the walkthrough asserts `SR-` appears nowhere in the response body. Decision log 2026-09-04 §1 |
| 5 | *"resolves to `1408 Elm St · A`, `· B`, `· Common` and `1412 Elm St`"* | The affected set is **PREMISES**: `1408 Elm St` and `1412 Elm St`, **two**, with **three units** on them, and the clerk's screen shows both figures. `22 Palm Ct` is not in it, which is the assertion that matters and is unchanged |
| 5 | *"adds the internal note and one customer-visible note"* | **No note is customer-visible today.** Every `service_request_events` row this product writes carries `internal=True` (`service_request_service._event`), so *"filter the timeline to the customer-safe half"* would today be a filter with nothing on the safe side. The tracked view therefore serves **no notes at all** and four dates instead — which satisfies step 7 by construction and is the honest shape until `US-CWP-062` builds the flag |
| 6 | *"`PAY-26-08841` + `78702` returns a payment's status and date"* | **Wave P's.** A payment's second fact is the postcode of the service address, three joins away through a `payments` seam that wave builds with quick pay itself. A payment reference is refused **identically to an unknown one**, which step 6's own rule requires of every wrong pair anyway — so the boundary is narrower than the journey asks and never wider. `selectors.TRACKABLE_SERIES` names the two that work |
| 9 | Planned work on `CWP-058`/`CWP-053` | **Not in this wave at all.** `US-CWP-011` is blocked on `OQ-249` and belongs to another wave; no `planned_outage` table exists and none is written |
| 11 | *"the form wrote an `interruption`, a `service_request`, a document and queue rows"* | Two rows, and **no document and no queue row** — see steps 3 and 4. The invariance itself holds and is asserted: `test_us_cwp_007_report.py` snapshots every account row before and after a guest write and compares them |

**What IS asserted in a browser, and where:** steps 1–8 and 10–11 of the table
above, in `cr068-b-report-and-track.mjs` — including the gas-smell case proved on
the DATABASE (the next reference the series hands out is the one after ours, so
the form consumed nothing), the eight keys of the track response read one by one,
the lock read off the screen in four words, and the affected set read off the
clerk's own table.

**Still NOT ACTIVATED as `07-frontend/e2e/J31.spec.ts`**, and the header above is
right about why: the wiring index is the authority and no spec file exists. The
walkthrough is the proof today.

---

## ⚠ AS BUILT AGAIN — 2026-09-04, `CR-072` (`2.140.0`), and it REVERSES one row of the table above

**The Product Owner saw the shipped behaviour on the live deployment and ruled it
out the same day**, verbatim: *"all the request coming from portal should go in
Service request. if we have to icnrease the defination of Service request we
should do it"*. This is a **supersession, not a correction** — the shape above was
built as designed, shipped, and is now wrong.

| Step | What wave B did | What `CR-072` does |
|---|---|---|
| 3 | One press of *Send* wrote **TWO** rows: a `service_requests` row and an `interruptions` row | It writes **ONE** — the service request. `problem_kind` carries what sort of problem, and `interruptions` is not touched at all |
| 4 | The reference on `CWP-007` is the **interruption's** `RP-26-0412`; the `SR-` is a clerk's vocabulary and is withheld | ⚠ **EXACTLY INVERTED.** The reference is the **request's** `SR-26-0049`, and the `RP-` series is never served to a guest. `BR-CWP-024` — *one reference, and it is theirs* — now points at the number of the record they actually asked for. The walkthrough asserts `RP-` appears nowhere in the response body, where it used to assert that of `SR-` |
| 5 | *"a clerk … moves the interruption to `crew_on_site`"* — the record already existed, because the form had made it | **A clerk OPENS it first** (`BR-CWP-101`). A stranger's form cannot settle whether a street is out. The section reads *"Nobody has opened an interruption for this yet"* with one commit; pressing it creates the record, and **many reports may attach to one** — the second report on the street is offered *Add to RP-26-0412* instead |
| 6 | `RP-26-0412` + `78702` is what a guest types | `SR-26-0049` + `78702`. `TRACKABLE_SERIES` narrowed to `("request",)`; the ANSWER still carries `series: "report"`, because that is the shape the screen draws and both shapes now come out of `service_requests`. **The eight keys of the response are byte-identical** — moving the record was not licence to widen what a stranger reads |
| 10 | RLS `FORCE` on `interruption` **and** `service_request` | Unchanged, and re-proved on the widened table under the NON-SUPERUSER probe role (`tests/test_cr072_pg.py`, `pg_class` read for both `relrowsecurity` and `relforcerowsecurity`) |
| 11 | *"the form wrote an `interruption`, a `service_request` …"* | **One row.** The invariance is unchanged and is re-asserted: `test_cr072_report_is_a_request.py` snapshots every account row before and after both the guest write AND the clerk's open |

**One thing the journey never said, and it nearly broke silently.** Step 3's
*"a second report from the same street is accepted and the screen says the street
is already reported"* was implemented as a scan of `interruptions`. Reports do not
write that table any more, so left alone it would have answered nothing for every
real second report — with every test green. It reads open REPORTS now, and a
confirmed interruption when there is one.

**The header's `RP-26-0412` and step 1's *"gets a reference"* are unchanged in
meaning and changed in value.** The journey's own fixture line still quotes
`RP-26-0412`; read it as the CLERK's number from `CR-072` onward, and
`SR-26-0049` as the guest's.
