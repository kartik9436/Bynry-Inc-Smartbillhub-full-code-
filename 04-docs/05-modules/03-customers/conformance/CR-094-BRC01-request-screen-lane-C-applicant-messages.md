# A service request can tell the applicant something — `CR-094-BRC01` lane C

**Built 2026-09-15.** Closes the queue half of `DEF-CUS-5389` and the whole of
`DEF-CUS-5391`. `DEF-CUS-5389` **stays OPEN** — its `surface` column names
`ServiceRequestDetailPage.tsx`, and the two modals are wave 2's.

---

## 0 · The gap, measured from the code before anything was built

**This was the first thing asked of this lane and it is the finding that shaped
everything else.**

**Nothing the product did with a service request ever reached the person who
raised it, and the cause of all three silences was one list.**
`apps/notifications/models.py` holds `SOURCE_TYPES`, a CONSTANT vocabulary of
the kinds of thing this platform can queue a message about. On 2026-09-15 it
held thirteen — `invoice · payment · notice · plan · report · ledger · test ·
bulk_action · move · account · portal · appointment · message` — and
`service_request` was not one of them. `services.queue_document` refuses an
unknown kind BY NAME, before it writes anything:

> `'service_request' is not a source kind this platform queues (invoice,
> payment, notice, plan, report, ledger, test, bulk_action, move, account,
> portal, appointment, message). The vocabulary is a CONSTANT, not a tenant
> lookup — a tenant cannot invent a source the platform has no writer for, and a
> row nothing recognises is a message nothing will ever send.`

**That sentence was printing on the request's own History tab, at a clerk, on
every submitted request in the demo tenant.**

**What it cost, and the third item is the one worth reading twice:**

| the drawing's promise | where it is drawn | what happened |
|---|---|---|
| *"A refusal letter is queued to the applicant"* | p085, the Refuse dialog's `WHAT REFUSING WILL DO` table | nothing was queued and there was nowhere to store what to say |
| *"A message is queued to them"* | p086, the Ask-for-more dialog's `WHAT THIS WILL DO` table | nothing was queued; the product recorded one fixed sentence, the same on every request |
| *"submitting sends the customer an acknowledgement"* | p086, the capture wizard's `Primary action` row | **the code for this existed, was wired, and was called on every single submission** |

**The third one is `DEF-CUS-5391` and it is the finding.** `BR-CUS-079` was
CONFIRMED by the PO on 2026-08-24 — *"when you take and submit SR - we have to
send email or text messge to customer"* — and `send_acknowledgement` was written
the same week. It caught the queue's refusal, wrote the reason on the timeline,
stored it on the row, served it to the screen and returned an honest absence.
Every one of those things is correct, and the feature had **never once worked**.
Its own test read `assert ack["state"] in (ACK_NOT_SENT, ACK_QUEUED)` and passed,
green, over three weeks of silence. The constant it depended on lived in another
module and the pair belonged to nobody.

### What the fix had to touch, and whether it was a multi-day change elsewhere

**It was not.** The measurement's own §9 said *"do not start with the
notification table … it cannot be built at all until `service_request` is a
source kind the platform queues — which is another module's change, and
cross-module writes are forbidden."* That reading is right about the boundary
and wrong about the size. Adding a source kind is a constant, a classification
in one test, template classes with their wording, and an entry-point module for
customers to resolve by name. **Publishing a seam in the module that owns the
table is exactly what the module map asks for** — what is forbidden is customers
writing `outbound_messages` itself, and it does not.

Measured before building: **7 things had to exist**, all of them small.

1. `service_request` in `models.SOURCE_TYPES` — 1 value.
2. Its classification in `test_cr048_print_floor.py`'s buckets — the second edit
   that gets forgotten, and `portal` proved it can be (`DEF-NOT-4032`).
3. Template classes and their palettes in `catalogs.py` — 4.
4. Their wording in `seed_templates.py` — 4.
5. An entry-point module in notifications, resolved BY NAME — new.
6. Three entry points on the existing `apps/customers/notifications_seam.py`.
7. Storage on `service_requests` for what a clerk types — 3 columns.

---

## 1 · Blueprint pages read, AS IMAGES, and at what scale

**Every page below was read with the Read tool as a PNG.** No screen copy, no
field list and no control name in this wave came from extracted text — B14 rule
42, and the PO's instruction of this date: *"I want you to use images only to
create screens - do not use text or content ot create product screens"*.

| page | what it carries | scale | how |
|---|---|---|---|
| `p084` | the Approve modal's tail, then the **Refuse** modal's head: title, sub-line, `WHY`, `Reason *`, `What to tell them` | **2** | pre-rendered `scratchpad/acct/p084.png` |
| `p084`, cropped to the Refuse modal | the five reason values and the two helper lines, legible | **4** | `10-scripts/pdf/pdf_render.py` at scale 4, then cropped to the modal so the reader did not downsample it away |
| `p085` | the Refuse modal's `WHAT REFUSING WILL DO` table and footer, then the **Ask-for-more** modal | **2** | pre-rendered |
| `p085`, cropped to the Ask modal | the four tick labels and the two helper lines, legible | **4** | as above |
| `p086` | the Ask modal's footer `Cancel` / `Ask and queue the message`, and the capture entry's `Primary action` row | **2** | pre-rendered |

⚠ **The scale-4 pages are 4896×3168 and the reader downsamples them**, which
throws away the detail the higher scale was rendered for. A crop script
(`scratchpad/crop.py`) renders the page at scale 4 and writes only the modal's
rectangle, so what was actually read is ~2230×860 at full resolution.

**What the images gave that the measurement's prose did not:** the exact helper
sentences (*"Goes into the refusal letter."* and *"Sent to them and kept on the
request's history."*), which is what settles whether the tick list is sent —
and the fact that the first tick reads *"A readable site plan — the one attached
was rejected"*, whose second half is an illustration of one request (B14 rule
37) rather than a label.

**This lane wrote no screen.** The drawings were read to fix the vocabulary, the
copy of the two helper lines and the shape of what the server accepts, so that
wave 2's modals have somewhere real to send what a clerk types.

---

## 2 · What wave 2 builds against — the exact payloads, with a worked example

### Refuse

```
POST /service-requests/{id}/refuse
{
  "reason":               "Duplicate — see SR-26-0004",     required, free text, internal
  "reason_code":          "duplicate_of_another_request",   optional, one of FIVE (below)
  "message_to_applicant": "We already have this request from you."   optional, becomes the letter
}
```

`reason_code` must be one of, and anything else is refused with the message key
`customers.serviceRequest.refusalReasonUnknown`:

| code | the drawing's label |
|---|---|
| `not_our_service_area` | Not our service area |
| `documents_not_provided` | Documents not provided |
| `applicant_withdrew` | Applicant withdrew |
| `duplicate_of_another_request` | Duplicate of another request |
| `other` | Other |

### Ask for more

Through the door every screen already calls — **no new endpoint**, deliberately
(see §4):

```
POST /service-requests/{id}/transitions
{
  "action":               "request_info",
  "reason":               "Site plan unreadable",           required, internal
  "info_needed":          ["readable_site_plan", "proof_of_identity"],   optional
  "message_to_applicant": "The site plan you sent will not open. Please send it again as a PDF."
}
```

`info_needed` must be a LIST drawn from, and anything else is refused with
`customers.serviceRequest.infoNeededUnknown` (a non-list gets
`customers.serviceRequest.infoNeededList`):

| code | the drawing's label |
|---|---|
| `readable_site_plan` | A readable site plan |
| `proof_of_identity` | Proof of identity checked and verified |
| `connection_date` | A connection date |
| `something_else` | Something else |

⚠ The drawing's first tick reads *"A readable site plan — the one attached was
rejected"*. The clause after the dash is an illustration of the one request in
the picture and would be false on a request with nothing attached, so the label
is the first half (B14 rule 37).

⚠ **The labels above are ENGLISH FOR THIS DOCUMENT and are not catalogue keys
yet.** This lane wrote no screen, so it minted no screen copy — three refusal
keys and nothing else went into the eleven catalogues. Wave 2 mints
`customers.serviceRequest.refusalReason.*` and
`customers.serviceRequest.infoNeeded.*` through `10-scripts/i18n_fanin.py`, from
the drawing, in each language's own vocabulary.

### What comes back, on both

Both answer the request detail with one extra key:

```json
"applicant_message": {
  "occasion": "refusal",
  "state": "queued",
  "reason": "no_delivery_adapter_in_this_product",
  "ref": "01a0a611-bbe0-7622-bdac-85f547fb97ec",
  "sent": false,
  "address": "sarah.miller@example.test",
  "template_code": "service_request_refused",
  "detail": "the refusal letter is on the outbound queue, addressed to the applicant. …",
  "problems": []
}
```

**`state` is `queued` or `not_sent`, and `sent` is `false` on every path and is
not a field anybody sets.** `reason` says why nothing went when nothing went:

| `reason` | what the screen should say |
|---|---|
| `no_refusal_message_was_written` | the clerk typed nothing, so no letter exists |
| `no_message_to_the_applicant_was_written` | the same, on ask-for-more |
| `applicant_supplied_no_email_address` | they gave a phone and no email |
| `applicant_message_refused` / `applicant_message_error` | the queue said no; the decision still stands |
| `no_delivery_adapter_in_this_product` | it IS queued — this is the reason it has not LEFT |

### And on the detail read

`decision_tab` now carries two new blocks, for wave 2 to render:

```json
"refusal":   {"reason_code": "duplicate_of_another_request",
              "reason": "Duplicate — see SR-26-0004",
              "message": "We already have this request from you."},
"more_info": {"needed": ["readable_site_plan", "proof_of_identity"],
              "message": "The site plan you sent will not open. …"}
```

⚠ **`reason_code` is a CODE and B14 rule 31 keeps a database value off a
screen** — wave 2 renders it through its own catalogue and never prints it.

---

## 3 · Before and after

| | before | after |
|---|---|---|
| kinds of message the platform can queue | 13 | **14** |
| template classes an applicant can receive | 0 | **4** |
| what a refusal stores about why | one free-text sentence, internal | a coded reason from five, the internal sentence, **and the applicant's own letter** |
| what asking for more sends | *"More information is needed before this can be reviewed."*, to nobody | the clerk's own words, to the applicant's email |
| acknowledgements queued since 2026-08-24 | **0** | one per submitted request |
| `decision_reason` on a refused request | never written | written |

---

## 4 · The judgments this lane made, where the rules ran out

Each is in the decision log of 2026-09-15 with its reasoning; they are listed
here so the next reader of this module finds them without a search.

1. **The idempotency key is the OCCASION, not the request.** The
   acknowledgement keys on the request (one per request; a replayed submit must
   write nothing). The refusal letter and the ask key on the
   `service_request_events` row recording the act, because a request asked twice,
   or refused → reopened → refused, would otherwise meet the unique key: the
   queue reports `created=False`, the clerk is told it was queued, and **the
   applicant is sent the first letter's contents and never the second's**.
2. **No print floor, and the reason is physical before it is a judgment.** This
   product holds **no mailing address for an applicant** — a request carries the
   address of the property wanting service — and the commonest drawn refusal
   reason is *Not our service area*. `BR-NOT-024` is a signed rule and a lane
   may not widen it by editing a dictionary (the `move` precedent).
3. **Email only.** All four classes are email; an SMS carries 160 characters and
   none of this wording is written for one. A phone-only applicant gets nothing,
   **named**.
4. **The tick list is not in the letter.** The drawing attaches *"Sent to them"*
   to the message box alone, and composing four ticks into English server-side
   would put untranslated prose inside a customer-facing document.
5. **The acknowledgement is two classes.** `BR-CUS-090` clause (3) cannot be
   satisfied by one body, because a template has no conditional in it.
6. **`request_info` was DELEGATED, not given a second door.** A new endpoint
   beside `refuse` would have left the door every screen already calls moving the
   state and telling the applicant nothing — hard-won law 2's mirror, a live
   control doing quietly less than the new one.

---

## 5 · Proof

Every case proved **RED first, in pytest — the harness that runs it** — one
break at a time, each reverted before the next. The tree was checked afterwards
for residue (`grep -rn "RED PROOF"` over `apps/` and `tests/` returns only other
lanes' historical notes).

| what was broken | what pytest said |
|---|---|
| `service_request` removed from `SOURCE_TYPES` | **10 failed, 10 passed.** First: `AssertionError: assert 'not_sent' == 'queued'` |
| the letter's call removed from `refuse_request` | **5 failed, 15 passed**, naming the four refusal cases and the savepoint case |
| the message keyed on the REQUEST instead of the act | `test_a_second_ask_writes_a_second_message_not_a_dedupe` → `assert 0 == 2`, and **zero is worse than one**: the ask deduped into the ACKNOWLEDGEMENT already queued on that request, so the applicant would have been sent *"we have your request"* when the clerk asked them for a site plan |
| the fee acknowledgement pinned unconditionally | `assert 'service_request_acknowledgement_fee' == 'service_request_acknowledgement'` on a request where no money was taken |

**Green:** `tests/test_cr094_service_request_messages.py` — **20 passed** in 25s,
`JOBS_EAGER=false --reuse-db`.

**Regression, same settings:** `test_cr031_service_request.py` ·
`test_cr048_print_floor.py` · `test_def_210_authored_template_bodies.py` ·
`test_us_cwp_063_track_request.py` · `test_cr048_b11_customer_events.py` —
**209 passed, 34 skipped, 3 failed**, and the three are named in §6.

`makemigrations --check` proposes **nothing** for `customers`, so `0047` covers
the model change exactly and the graph has one leaf.

⚠ **WHAT WOULD MAKE THESE CASES PASS WRONGLY**, asked of each before it was
trusted (law 7, habit 2): the dangerous false pass is a case that asserts a queue
ROW exists and never looks at what is in it or who it is addressed to — a row
addressed to nobody, or carrying the wrong body, satisfies that. So every case
reads the row back: `recipient_address`, the pinned `template_code`, and the
clerk's words inside `render_context`.

### Nothing was sent to anybody, and where a real deployment would send it

`BR-NOT-013` — no provider adapter exists on any channel — so every message is a
row on `outbound_messages` and nothing leaves the building. **A real deployment
delivers to `outbound_messages.recipient_address`, which is the applicant's own
email exactly as it was typed on the request** (`service_requests
.applicant_email`), snapshotted at queue time per `BR-TEN-017`. No write path in
this wave touched the shared demo tenant: every proof is a pytest fixture
building its own request.

---

## 6 · Reds I did not cause, with their dates

⚠ **This worktree's history is grafted at `2db4d169` (2026-09-13), so
`git log -S` cannot date anything older than that.** Where it could not, the
date comes from the repo's own record and is named as such.

| red | dated | filed |
|---|---|---|
| `test_cr048_b11__the_account_kind_carries_the_print_floor` — asserted *"the four kinds that genuinely keep no floor"* and listed four | **RED SINCE 2026-09-04**, from the constant's own comments: `portal` joined 2026-09-04, `appointment` 2026-09-05, `message` 2026-09-12, none of them added to this assertion. **Eleven days, four kinds, three lanes past it.** | **FIXED HERE** — I was about to be the fourth, and the count is gone from the prose because a sentence carrying a number goes stale the next time the number moves |
| `test_def_210__every_seeded_class_has_a_catalogue_and_a_listing[email_statement / email_past_due / email_payment_receipt]` — `'Statement · Email' != 'Statement · email'` on three classes | **UNDATEABLE** (older than the graft). Not mine: `git diff` shows this lane touched none of the three names | **`DEF-NOT-5392`** — left red, because both strings reach a System Admin on Settings → Templates and which one is right is a copy decision belonging to that screen's owner, not to a passing lane |
| `test_the_list_is_oldest_first_and_segments_by_state` and `test_us_cus_025_tc2_the_list_is_oldest_first` | **RED SINCE 2026-09-12**, from `service_request_reads.py`'s own docstring: `BR-CUS-1046` / `DEF-CUS-5060` made the Requests list open newest-first that day and left oldest-first as a column a clerk clicks. The two cases were never amended | **`DEF-CUS-5393`** — left red; the fix is a rename as much as an assertion, and a case still called `oldest_first` that asserts newest-first is the next reader's trap |
| `makemigrations --check` proposes a `rating` constraint rewrite (`ck_discount_versions_scope`) | `git log -S` → `ac3bd496`, **2026-09-10** | not filed — outside this module and not re-checked by this lane against the register |

**The product builds.** Nothing here stops the next lane working (skill §10's
test), which is why the two register rows are the right answer for the two that
stay red rather than a fix made on somebody else's authority.

---

## 7 · What is NOT built, and why

| | |
|---|---|
| **The Refuse modal and the Ask-for-more modal** | wave 2's. `DEF-CUS-5389` stays OPEN and its `surface` column already names the screen file. Everything the modals need to send is in §2. |
| **Step 6's table of five messages with a template picker** | the capture wizard's `What goes out to the applicant` block and its `Choosing a template` table (p080–p081). **Measured, not started**, as instructed. It needs the five occasions named and ruled, a per-tenant switch for each, and the picker reading the tenant's own registry. It is its own piece of work and it now has a foundation: the source kind exists, so the table has something real to switch. |
| **SMS wording for any of the three** | an SMS is 160 characters and none of these letters is written for one. An applicant who leaves a phone and no email is recorded as `applicant_supplied_no_email_address` and gets nothing. |
| **A Settings switch for the acknowledgement** | no `event_key` is passed on any of the three. The two clerk-triggered messages must never be silently swallowed by a rule, and the acknowledgement is a ruled obligation (`BR-CUS-079`) rather than a courtesy. Making it switchable is a `BR-CUS-079` question for the PO. |
| **Catalogue keys for the five reasons and the four ticks** | this lane wrote no screen, so it minted no screen copy. §2 carries the English; wave 2 fans them into the eleven. |

⚠ **One thing noticed and not acted on:** the four new classes file under
`CAT_ACCOUNT_LIFECYCLE`, which is one of the three categories the account
Communication dialog offers as starting wording. So a clerk composing a message
to an ACCOUNT can pick *"Service request refused"* as a starting point. It is
not broken — the tokens this screen cannot answer blank to `____` — but it is an
odd offer, because these four are addressed to an applicant and that dialog
composes to an account holder. Recorded rather than filed: narrowing
`OFFERABLE_TEMPLATE_CATEGORIES` changes another screen's behaviour on this
wave's authority.
