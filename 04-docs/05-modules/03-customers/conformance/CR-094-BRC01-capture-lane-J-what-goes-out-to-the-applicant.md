# What goes out to the applicant, and the decision that never went — `CR-094-BRC01` lane J

**Built 2026-09-15.** Builds `BR-CUS-1076`. Files `DEF-CUS-5417`.

**This lane wrote no screen.** `ServiceRequestCapturePage.tsx` is lane D's this
wave. §2 publishes the payload and the table shape with a worked example so D
builds from the repo and not from a conversation.

---

## 0 · The gap, measured from the code before anything was built

The Product Owner asked, verbatim:

> *"at the time of approval we are also linking notification and templates to
> the modal - are you ensuring it will work?"*

**The honest answer was no, and it was no in three separate ways.**

| what the drawing promises (p080) | what the product did on 2026-09-15 morning |
|---|---|
| a request carries five messages it may send, three ticked | **no table, no column, nothing.** A request could not remember a single one |
| a clerk picks the wording for each from a list | **no template choice existed on a request at all** |
| row five: *"The decision, when it is made · On approve or refuse"* | **refusing wrote to them** (lane C, that morning) and **approving fired nothing** |

The third one is the finding. Somebody could apply for service, be approved, and
never hear a word — while the *refusal* path had been writing to them for hours.
The half of the drawn row that reached a customer with good news was the half
that did not exist.

### What had to be true before any of it could be built, checked against the code

Lane C's record said the block *"needs the five occasions named and ruled, a
per-tenant switch for each, and the picker reading the tenant's own registry."*
**Two of those three readings turned out to be wrong when measured, and the
third had already been built by somebody else:**

1. **"named and ruled"** — nothing in the decision log or the open questions
   rules on the five occasions (grepped both, per law 13). So they are **ours to
   decide and write down**, which is what §4 is.
2. **"a per-tenant switch for each"** — no. A per-tenant switch is
   `queue_document`'s `event_key`, and the drawn control is a **per-REQUEST
   tick a clerk sets at the counter**. Two switches over one message is how a
   clerk ends up unable to say why nothing went; the tenant switch is not built
   and is named as absent.
3. **"the picker reading the tenant's own registry"** — right, and the registry
   was already there: `notification_templates` carries exactly the drawn columns
   (`name`, `group`, `channel`, `category`, `language`) and
   `notification_template_versions` carries the version and its
   `draft`/`published` status. Nothing new had to be modelled for the picker.

**And the biggest single finding is that one of p081's four rules was already
law and already built:** *"A template resolves on three axes and falls back on
two"* **is `BR-BIL-025`**, implemented in `template_service.resolve`, which is
the same call the dispatcher makes. This lane verifies it rather than
reimplementing it — a second resolver would have been two rules that agree
today.

---

## 1 · Blueprint pages read, AS IMAGES, and at what scale

**Every page below was read with the Read tool as a PNG.** No control name, no
column, no default and no rule in this wave came from extracted text — B14 rule
42, and the PO's instruction of this date: *"I want you to use images only to
create scereens - do not use text or content ot create product screens"*.

| page | what it carries | scale | how |
|---|---|---|---|
| `p080` | capture step 6's two columns; **`What goes out to the applicant`** — the five rows with their `SEND · WHAT IT SAYS · TO · CHANNEL · TEMPLATE · WHEN` columns; **`Choosing a template`** — the search box, its helper line, and the picker's five columns with a radio per row; and the block's closing line | **2** | pre-rendered `scratchpad/acct/p080.png` |
| `p081` | the **four rules** above the page break that govern the block, then the wizard footer and `Where a captured request lands` | **2** | pre-rendered `scratchpad/acct/p081.png` |

**What the images gave that prose could not:** the exact tick pattern (**three of
five**, and *which* three), the three distinct `WHEN` values, the draft row
sitting in the picker **with its radio drawn empty rather than absent**, and the
`— none chosen` in row four's template column — every one of which is a design
decision that survives only as a picture.

⚠ **THE DRAWN FIGURES ARE ILLUSTRATIONS AND NONE OF THEM IS BUILT** (B14 rule
37). `$25.00`, `$105.00`, `v6`, `v4`, `v2`, `SR-26-0001`, `Miller, Sarah` are
the one request in the picture. What is built is the SHAPE: five rows, three
moments, a class, a variant and a version number read from the tenant's own
registry.

---

## 2 · What lane D builds against — the exact shapes, with a worked example

### The table

`service_request_messages`, one row per (request, occasion). **Four columns are
choices and the rest is what happened.**

| column | what it is |
|---|---|
| `occasion` | one of five (below) |
| `send` | the drawn `SEND` tick |
| `template_code` | the class the clerk picked, or NULL for `— none chosen` |
| `template_id` | the exact VARIANT row they picked, used as `BR-BIL-025`'s `override_template_id` |
| `template_version_seen` | the number the picker was showing — **evidence, never a pin** |
| `fired_at` / `fired_state` / `fired_reason` / `fired_ref` / `fired_template_code` | what happened, and which queue row carries it |

**Four drawn columns are NOT stored and are read instead:** `TO` (the
applicant's name, on the request), the request number (on the request),
`CHANNEL` (**the template class's own fact** — notifications publishes it beside
each picker row) and `WHEN` (**the occasion's own fact**, a constant). Hard rule
8's reasoning one table over: a fact has one home and everything else walks to
it.

### The five occasions, and the three moments

| `occasion` | the drawn row | `when` | ticked by default | wording exists |
|---|---|---|---|---|
| `request_received` | *The request is in, and its number* | `on_submit` | ✔ | **yes** — two classes, picked by whether a fee was taken |
| `documents_outstanding` | *What we still need from them* | `on_submit` | ✔ | **no** — `DEF-CUS-5417` |
| `counter_receipt` | *A receipt for what was taken* | **`already_handed_over`** | ✔ | n/a — **it never queues** |
| `balance_outstanding` | *That a balance is still owed* | `on_submit` | ✘ | **no** — `DEF-CUS-5417` |
| `decision` | *The decision, when it is made* | **`on_approve_or_refuse`** | ✘ | **yes** — two classes, picked by the outcome |

### `GET /service-requests/{id}/applicant-messages`

Answers all five whether or not anything is stored — the defaults are a
constant, so a request nobody has touched and a request that predates the table
both answer correctly rather than answering empty.

```json
{
  "rows": [
    {
      "occasion": "decision",
      "when": "on_approve_or_refuse",
      "send": true,
      "send_is_default": false,
      "template_code": "service_request_approved",
      "template_id": "01a0a611-bbe0-7622-bdac-85f547fb97ec",
      "template_version_seen": 2,
      "available": true,
      "queues": true,
      "must_be_in_writing": true,
      "classes": ["service_request_approved", "service_request_refused"],
      "fired_at": null, "fired_state": null, "fired_reason": null,
      "fired_template_code": null,
      "sent": false
    }
  ],
  "delivery": {"queued_only": true, "delivers": false, "br_ref": "BR-NOT-013"}
}
```

⚠ **`available` IS THE ONE LANE D MUST RENDER.** Two of the five rows come back
`available: false`, and the drawn default for one of them is **ticked**. A tick
over a row nothing can send is hard-won law 2's mirror, so the screen has to say
so rather than draw a promise.

⚠ **`template_id` IS A DATABASE ID AND IS NEVER THE VISIBLE VALUE OF A FIELD**
(B14 rule 31). It travels so the picker knows which radio is filled. What a
clerk reads is `name`.

### `PUT /service-requests/{id}/applicant-messages`

```json
{"rows": [
  {"occasion": "decision", "send": true,
   "template_code": "service_request_approved",
   "template_id": "01a0a611-bbe0-7622-bdac-85f547fb97ec",
   "template_version_seen": 2}
]}
```

Send the rows the clerk touched, or all five — both work. Answers the same shape
as `GET`. **Four refusals, each by message key**, so the screen renders a
sentence rather than meeting silence:

| message key | when |
|---|---|
| `customers.serviceRequest.messageOccasionUnknown` | an occasion this product does not have |
| `customers.serviceRequest.messageTemplateNotForOccasion` | a class this occasion does not send |
| `customers.serviceRequest.messageTemplateNotPickable` | a DRAFT was picked (p081 rule 2) |
| `customers.serviceRequest.messageTemplateNotInWriting` | a text was picked for the decision (p081 rule 3) |

⚠ **ALL SEVEN REFUSAL KEYS ARE ALREADY IN ALL ELEVEN CATALOGUES, AND THAT WAS
NOT THE PLAN — THE CODE CORRECTED IT** (skill §0: check the rule against the
code). This lane wrote no screen, so it intended to mint no copy and leave the
keys to lane D. **`core/errors.py` refuses a refusal whose key no catalogue
defines, AT RAISE**, with the sentence *"this refusal would reach a clerk as
SILENCE — the click does nothing and no sentence appears anywhere. 57 of these
shipped in the Work module alone."* Four of this lane's own cases went red on
it. So the seven went in through `10-scripts/i18n_fanin.py`, translated in each
language's own vocabulary (B14 rule 35), each sentence within rule 33's
six-word cap. **Parity proved: 17,791 → 17,798 keys, +7 / −0 in every one of the
eleven.**

The three not in the table above are the shape refusals:
`customers.serviceRequest.messageOccasionUnknown`,
`...messageTemplateUnknown` and `...messageTemplateVersion`.

⚠ **THE SCREEN'S OWN COPY IS STILL LANE D'S** — the row labels (*The request is
in, and its number*, and the other four), the column headings and the picker's
help line are screen copy this lane deliberately did not mint. They are drawn on
p080 and must be built from the image, not from this file, and **the drawn
figures in them are illustrations** (B14 rule 37): the label is *a receipt for
what was taken*, never *"a receipt for the $25.00 taken"*.

### `GET /service-requests/{id}/applicant-message-templates?occasion=decision&search=…`

```json
{
  "occasion": "decision",
  "available": true,
  "reason": null,
  "rows": [
    {"template_id": "01a0…", "code": "service_request_approved",
     "name": "Service request approved", "group": "email", "channel": "email",
     "category": "default", "language": "default",
     "version": 1, "status": "published",
     "pickable": true, "not_pickable_reason": null, "is_writing": true},
    {"template_id": "01a0…", "code": "service_request_approved",
     "name": "Service request approved · large print", "group": "email",
     "channel": "email", "category": "commercial", "language": "default",
     "version": 1, "status": "draft",
     "pickable": false, "not_pickable_reason": "nobody_has_published_this_version",
     "is_writing": true}
  ],
  "delivery": {"queued_only": true, "delivers": false, "br_ref": "BR-NOT-013"}
}
```

⚠ **THE DRAFT ROW MUST BE RENDERED, DISABLED — FILTERING IT OUT IS THE ONE
BEHAVIOUR THE RULE FORBIDS.** p081, read as an image: *"The draft version is
listed and cannot be picked. Hiding it sends a clerk looking for something they
can see exists; offering it would queue a letter nobody has approved."*

⚠ **`search` MATCHES THE NAME AND NEVER THE CODE** — the box's own helper line
is *"Searches the name a human gave it."*, and a clerk cannot search by a value
B14 rule 31 never lets them see. `search="service_request_"` returns **zero
rows**, which is a case in the suite.

The drawn `VARIANT` column is `category · language`, which the screen composes
in its own catalogue (*Default · English*) and never from these raw values.

### What comes back when a request is approved

`POST /service-requests/{id}/approve` answers the detail plus `job` — unchanged
— **and now `applicant_message`**:

```json
"applicant_message": {
  "occasion": "decision", "when": "on_approve_or_refuse",
  "state": "queued", "reason": "no_delivery_adapter_in_this_product",
  "ref": "<the outbound_messages row>",
  "template_code": "service_request_approved",
  "sent": false, "replayed": false,
  "delivery": {"queued_only": true, "delivers": false, "br_ref": "BR-NOT-013"}
}
```

`state` is `queued` or `not_sent`. **`sent` is False on every path and is not a
field anybody sets.** `reason` says why nothing went when nothing went:

| `reason` | what the screen should say |
|---|---|
| `the_clerk_did_not_ask_for_this_one` | row five was left unticked |
| `this_product_has_no_wording_for_this_one_yet` | no class for that occasion |
| `the_receipt_was_handed_over_at_the_counter` | it was never going to be queued |
| `no_delivery_adapter_in_this_product` | it IS queued — this is why it has not LEFT |
| `this_one_had_already_gone` | a replay; one message, not two |

### The worked example, end to end

A clerk captures Sarah Miller's application at the counter and, on step 6, ticks
row five and leaves the wording at the utility's published default:

```
PUT /brazosbend/service-requests/<id>/applicant-messages
{"rows": [{"occasion": "decision", "send": true}]}
```

Four days later a supervisor approves it:

```
POST /brazosbend/service-requests/<id>/approve
```

**One** row appears on `outbound_messages`, `source_type='service_request'`,
`source_id=<the request>`, `template_code='service_request_approved'`,
`recipient_address='sarah.miller@example.test'`, with a real
`template_version`. The decision row reads
`fired_state='queued' · fired_template_code='service_request_approved'`.
Approving again — a retried call, a double-clicked button — answers
`replayed: true` and **the queue still holds one row, not two.**

Had she been REFUSED with a letter instead, **no second message is queued**: the
refusal letter the clerk typed is row five on that path, and the decision row
carries that letter's own `ref`.

---

## 3 · Before and after

| | before | after |
|---|---|---|
| messages a request can remember | **0** | **5**, three ticked as drawn |
| template classes an applicant can receive | 4 | **5** |
| what approving told the applicant | **nothing** | one email, queued, addressed to them |
| what a clerk could choose about any of it | **nothing** | the tick and the wording, per row |
| p081 rules with something enforcing them | 1 of 4 (resolution, via `BR-BIL-025`) | **4 of 4** |
| occasions with no wording | — | **2 of 5**, each saying so on its own row |

---

## 4 · The judgments this lane made, where the rules ran out

All six are in the decision log of 2026-09-15 with their reasoning, written
**before** the code that depends on them (step W). They are listed here so the
next reader of this module finds them without a search.

1. **Refusing queues no second letter, because the refusal letter IS row five on
   that path.** The tick is a standing instruction and a clerk in front of the
   request outranks it.
2. **The decision is one occasion with two classes and the OUTCOME picks** — a
   template body has no conditional in it, which is why lane C split the
   acknowledgement in two that same morning. A pick for the other half stands
   down and the row records both.
3. **The version is not pinned at capture** — the class and the variant are
   stored, the number shown is evidence, and resolution happens at queue time
   through `BR-BIL-025`.
4. **No channel column and no `when` column** — both are facts that already have
   a home.
5. **The approval letter keys on its own timeline row.** ⚠ **This one was
   written the other way round first, and it was wrong** — see §6.
6. **Asking for more fires nothing here** — it is not a decision.

---

## 5 · Proof

Every case proved **RED first, in pytest — the harness that runs it** — one
break at a time, each reverted before the next.

| what was broken | what pytest said |
|---|---|
| `applicant_messages.on_decision(...)` removed from `approve_and_raise` | **6 failed, 15 passed.** First: `AssertionError: assert 'not_sent' == 'queued'`, then `assert 0 == 1  +  where 0 = len([])` — an empty queue on an approved request, which is the defect this lane closes |
| the `fired_at` guard removed from `on_decision` | `test_approving_twice_queues_one_not_two` → `assert False is True` on `replayed` |
| `_pin`'s override honoured even when the picked variant is the other class | **first attempt stayed GREEN** — see §5's *what this lane got wrong*. With the case corrected to assert the `template_id`: `AssertionError: assert '01a0a687-af4e-…' != '01a0a687-af4e-…'` |
| `_refuse_unpickable`'s `pickable` check removed | `test_a_draft_version_is_listed_and_cannot_be_picked` → `Failed: DID NOT RAISE ValidationError` |
| the in-writing guard removed (p081's *"A text never replaces a posted notice"*) | `test_a_text_can_never_carry_the_decision_on_its_own` → `assert True is False` |
| `refuse_request` sending `already=` away, so the refuse path queues its own second letter | `assert [<OutboundMessage …>] == []  Left contains one more item` — **two letters about one decision**, which is exactly what judgment (1) exists to prevent |

Each break was reverted before the next, and the suite was re-run green after
every revert (**24 passed**, `JOBS_EAGER=false --reuse-db`, ~30s).

**Green:** `tests/test_cr094_applicant_messages_block.py` — **24 passed**.

**Regression, same settings:** eight neighbouring files —
`test_cr094_service_request_messages.py` · `test_cr094_approval_raises_the_job.py`
· `test_cr031_service_request.py` · `test_cr031_service_request_api.py` ·
`test_cr048_print_floor.py` · `test_def_210_authored_template_bodies.py` ·
`test_cr048_b11_customer_events.py` · `test_cr094_request_place_and_units.py` —
**330 passed, 36 skipped, 9 failed**, and every one of the nine is accounted for
in §6: **four were counts this lane moved and are now green**, three are a
sibling lane's from this morning (`DEF-CUS-5418`) and three are lane C's
(`DEF-NOT-5392`).

`makemigrations --check` proposes **nothing for `customers`**, so `0051` covers
the model change exactly and the graph has one leaf.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY**, asked of each before it was trusted
(law 7, habit 2). Three false passes are available here and each is closed:

* **A case that asserts a queue ROW exists and never reads it.** A row addressed
  to nobody, or carrying the refusal letter, satisfies that — so the approval
  cases read `recipient_address`, `template_code`, `template_id` and
  `template_version` back off the row.
* **A case that counts rows for the whole tenant.** Every count is filtered to
  ONE request's `source_id`, because a sibling fixture queueing an
  acknowledgement would otherwise make *"exactly one"* true or false by
  accident.
* **A case that proves idempotency through a door that refuses the second call
  anyway.** `approve` refuses an already-approved request, so *"approving twice
  queues one"* proved through `approve` would be proving the state machine and
  not the key. The case calls `on_decision` directly — the path a retried HTTP
  call, a double-clicked button and a replayed job all reach.

### Nothing was sent to anybody

`BR-NOT-013` — no provider adapter exists on any channel — so every message is a
row on `outbound_messages` and nothing leaves the building. **A real deployment
delivers to `outbound_messages.recipient_address`, which is the applicant's own
email exactly as it was typed on the request**, snapshotted at queue time per
`BR-TEN-017`. No write path in this wave touched the shared demo tenant: every
proof is a pytest fixture building its own request.

### ⚠ What this lane got wrong, and what caught it

**Two things, and both were caught by doing what the skill says rather than by
any gate.**

**1 · The approval letter was first keyed on the REQUEST, and that collides with
the acknowledgement.** The reasoning was tidy and false: *a request can be
refused, reopened and refused again, so the refusal keys on its timeline row; a
request is approved once, so the approval can key on the request.* But the
acknowledgement already keys on the request, and the queue's key is (tenant,
source kind, source id, channel, copy no) — so the approval letter met the
acknowledgement's own row, `queue_document` answered `created=False`, and **the
applicant would have been sent *"we have your request"* on the day they were
approved.** The state came back `queued` with a real `ref`; the ref was the
acknowledgement's. Lane C's docstring describes this exact trap for the ask —
written that morning, read by this lane, and walked into anyway. It was caught
because the case reads the queue row back instead of trusting the returned
state.

**2 · `test_a_pick_for_the_other_half_of_the_decision_stands_down` could not
fail.** Its first draft asserted the queued row's `template_code`, and `_pin`
stamps the code it was ASKED for while taking the id and the version from what
resolved — so a row pinned to the refusal variant's BODY still reads
`service_request_approved` in its code column. **With the guard deleted the case
stayed green.** It now asserts the `template_id`, and it goes red. That is law
7's fourth shape — a check looking at the wrong thing — and the only reason it
was found is that the guard was broken on purpose before being trusted.

---

## 6 · Reds I did not cause, with their dates

⚠ **This worktree's history is grafted, so `git log -S` cannot date anything
older than 2026-09-13.** Where it could, the command and its answer are below.

| red | dated, and how | what this lane did |
|---|---|---|
| `black --check` would reformat `apps/customers/service_request_api.py` and `service_request_service.py` | **RED AT THE PINNED TIP `ce2fc2f6` (2026-09-15)**, proved rather than assumed: the tip's OWN bytes (`git show ce2fc2f6:<path>`) were written to a scratch directory and `black --check` run on them — both would reformat before this lane existed. None of black's complaints is in a hunk this lane wrote. | **LEFT.** The reformats sit inside hunks four sibling lanes are editing right now, and rewriting them is the whole-file write law 11 exists to prevent. |
| `makemigrations --check` proposes a `rating` constraint rewrite (`ck_discount_versions_scope`) | `git log -S "ck_discount_versions_scope" -- 06-backend/apps/rating/` → **`ac3bd496`, 2026-09-10** | left — another module, and lane C reported the same one this morning. **Nothing is proposed for `customers`.** |
| `test_cr031_service_request.py::test_br_cus_092_the_ssn_is_captured_and_the_rest_stay_refused` · `::test_us_cus_024_tc9_an_identifier_field_is_refused_by_name` · `test_cr031_service_request_api.py::test_the_detail_states_what_it_cannot_answer` | `git log -S "drivers_licence_stored_encrypted" -- 06-backend/apps/customers/` → **`24bcc674`, 2026-09-15** — the sibling lane that landed the driving licence hours before this one. All three enumerate a closed set the licence moved, and none was amended. This lane touched no SSN or licence code. | **FILED as `DEF-CUS-5418`** and left. The fix is three assertions moving with the fields, which belongs to whoever owns `BR-CUS-092`. |
| `test_def_210__every_seeded_class_has_a_catalogue_and_a_listing[email_statement / email_past_due / email_payment_receipt]` — `'Statement · Email' != 'Statement · email'` | lane C filed it this morning as **`DEF-NOT-5392`** | left — already routed, and which of the two strings is right is a copy decision on Settings → Templates. |
| **47 failing gates** on `run_gates.py --changed`, of which **45 name nothing this lane touched** | the FULL output (not a `tail`) was searched for every path this lane wrote and for `BR-CUS-1076`, `DEF-CUS-5417`, `applicant_message*`, `service_request_messages`, `applicant_templates`, `service_request_approved`, `0051_`, `0052_`. `G106 cited-ids-exist`, which refuses an id no register ever issued, names five and none is this lane's. | left, and named here so a reader can see they were looked at rather than skipped. ⚠ **The first read of this output was a `tail -35` and showed only 8 of the 47** — which would have been a confident *"none of them is mine"* over 39 gates nobody had looked at. The run was repeated with the whole stream captured. |

### Two gate failures that WERE this lane's, found by reading the full output

| gate | what it said | fixed |
|---|---|---|
| `G7 human-owned` | `customers/0051` **lacks the HUMAN-OWNED marker**. Migration ordering is a 🔒 path in `CLAUDE.md` and `0052` carried the marker while `0051` did not. | the marker is on it. (`G7` names `customers/0045` for the same thing; that one is a sibling's and is left.) |
| `G53 guard-list-coverage` | `applicant_message_models.py` **invokes the 🔒 protocol in its own docstring, matches no glob in `human_owned.txt`, and has no ledger row** — and the gate says in its own words that *"adding a file to that list is a PROCESS EVENT and the PO's call, not a lane's — file it and say so, never add yourself."* | **the claim was withdrawn rather than the list widened.** The 🔒 paths here are the two MIGRATIONS, which are their own files, both marked, and both on one ledger row. The model module is an ordinary Django model and now says so, naming the two files that do carry the protocol. A file invoking a protocol nothing enforces is hard-won law 1 in one line. |

### Four counts that ARE this lane's, and were moved rather than left red

Adding a template class and two seam names moved four assertions that name a
number. Each one is the check working exactly as intended — a figure in a test
is what tells the next lane the world changed — so each was moved with its
reason beside it, in one line:

| case | from | to |
|---|---|---|
| `test_cr094_service_request_messages.py::test_the_seam_reaches_three_real_functions` | three names | five, **and the case is renamed `…_reaches_every_published_name`** — the count was IN THE NAME, which is B14's rule-count rot in a test |
| `test_def_210__the_library_covers_…::assert len(listed)` | 43 | 44 |
| `test_def_210__the_library_covers_…::assert len(seeded)` | 38 | 39 |
| `test_def_210__provisioning_publishes_an_email_variant_with_a_subject::assert expected` | 25 | 26 |

⚠ **One thing noticed and NOT acted on:** that second case is named
`…_covers_thirty_one_of_the_thirty_six_listed_classes` while its assertion reads
44. The name was already stale before this lane arrived and renaming another
lane's case is not a passing lane's call — recorded here so the next reader
knows it is known.

### One red this lane FOUND while re-deriving, and did not cause

⚠ **A LOCALE KEY WAS DELETED WHILE ITS SCREEN WENT ON ASKING FOR IT**
(`DEF-CUS-5419`). `customers.serviceRequest.applicant.driversLicenceAbsent` is
**present in all eleven catalogues at `ce2fc2f6` and absent at `a8b92161`**,
while `ServiceRequestCapturePage.tsx` still calls it — so a clerk reading that
screen is shown the key's own name.

**It surfaced only because this lane re-derived its catalogues from the tip.**
`G27 i18n-keys` was GREEN on the first gate run — over catalogues that still
held the key — and went red on the second, after the re-derivation. A lane
working from an older base sees green, which is how it reached the branch.

**Filed, not fixed.** That file is another lane's this wave and the missing
string is customer-facing copy in eleven languages — inventing it would be
exactly the guess this repo files questions about. It is `DEF-CUS-3653`'s own
lesson, which `CLAUDE.md` already records: *before retiring a value, grep for
its CONSUMERS, because an absence is invisible to every check this repo has.*

### One noise source that is not a failure

Every run of any case that approves a request prints
`kombu … Error 111 connecting to localhost:6379` from the jobs dispatcher.
There is **no Redis on this machine** and `JOBS_EAGER=false` sends jobs to the
broker, so any path raising background work logs it. It fails nothing — the job
row stays queued, which is what the dispatcher's own message says — and it is
absent from suites that never approve anything.

---

## 7 · What is NOT built, and why

| | |
|---|---|
| **The screen** | `ServiceRequestCapturePage.tsx` is lane D's this wave and this lane did not open it. Everything it needs is in §2. |
| **Wording for `documents_outstanding` and `balance_outstanding`** | `DEF-CUS-5417`. Two of the five. The first needs a class and a body; the second is money and the fee step has two questions still with the PO, so guessing its wording would be guessing what a balance letter may say about a receipt nobody has ruled on. |
| **Firing anything `on_submit`** | Row one already fires — it is `BR-CUS-079`'s acknowledgement and has since lane C landed. Rows two and four cannot fire because they have no wording. **Nothing in this lane touched `submit`**, deliberately: four sibling lanes are live in `apps/customers` and `submit` is the most-called function in the module. |
| **A per-tenant switch for any of the five** | The drawn control is a per-REQUEST tick. A tenant switch is `queue_document`'s `event_key` and would be a SECOND switch over one message — which is how a clerk ends up unable to say why nothing went. If a utility asks for one, it is a `BR-CUS-1076` amendment, not a keyword quietly added. |
| **SMS wording for the decision** | The drawing shows row five going `Email · SMS`, the text riding *"alongside it and never instead of it"*. No SMS wording exists for any of these five classes; an SMS carries 160 characters and none of this is written for one. The courtesy half is **absent, named**, and the guard in §2 is what stops that absence becoming a substitution. |
| **The screen's own copy** | The five row labels, the column headings and the picker's help line are drawn on p080 and are lane D's to mint from the image. The seven REFUSAL keys are already in all eleven (§2) — the code refused to raise without them. |
