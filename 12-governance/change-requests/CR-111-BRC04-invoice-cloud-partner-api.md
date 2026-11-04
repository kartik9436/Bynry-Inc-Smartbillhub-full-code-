# `CR-111-BRC04` · The Invoice Cloud API reference — five rulings, one that removes a partner's ability to write money to us, and one that reverses another the same day

| | |
|---|---|
| Raised | 2026-09-17 |
| Requester | Product Owner, in the working chat session |
| Branch | `claude/gifted-johnson-top7zn` · block `CR-110`–`CR-114`, suffix `BRC04` |
| Module | integrations · payments |
| Classification | **CHANGE** on rulings 2 and 5 · **CONFIRMATION** on rulings 3 and 4 · **ruling 1 is SUPERSEDED by ruling 5 the same day and was never built** |
| Version | allocated at build time through `allocate.py version --bump change` |
| Status | **CAPTURED AND RULED 2026-09-17. NOTHING BUILT** — this is the record landing before the thing that depends on it (build process step W) |
| ⚠ Read first | **FIVE rulings, not four, and ruling 2 was NARROWED by the Product Owner the same day** — *"batch run"* is a scheduled call to Invoice Cloud's API, **not a file** (§0, §2, §6). The fifth ruling **REVERSES ruling 1**. Ruling 1 is kept as recorded, stamped, because `serve.py`'s docstring still quotes the 2026-09-16 sentence it superseded and a reader tracing that quotation needs the middle link. **`BR-INT-070` carries the current law.** |

---

## 0 · Capture — the requester's words, verbatim

The Product Owner supplied the **Invoice Cloud integration's API reference** (their partner,
SMART360 ↔ Invoice Cloud) and then answered four questions put to them in plain English. The
reply, quoted exactly as sent, in one message:

> *"company_id = Keys will esnure it map to tenant ID; Can a partner post a payment at all? - I
> want to use batch run  to take payment feed from Them - not online updates; Can a partner waive
> a late fee? - no; Overpayment → credit note, on their say-so? yes"*

⚠ **THE SPECIFICATION DOCUMENT ITSELF IS NOT IN THIS REPOSITORY.** It was supplied in the chat
session and no copy is on any branch — `git ls-tree -r --name-only <ref> | grep -i 'pdf$'` across
the refs finds the six blueprints and nothing else. **So everything a lane needs from it is
written out here rather than cited**: the four questions as they were put, the field names the
document carries, and what each ruling settles. A lane must not go looking for the document; it
is not there, and this file is the record.

### The four questions, as they were put to the Product Owner

They were put in plain English with a concrete figure or a concrete field name, never as an ID to
go and look up (the standing instruction, `CLAUDE.md` 🔒 *What counts as that sign-off*):

1. **"`company_id` = 393, or our own id?"** — Invoice Cloud's document sends `company_id=393`,
   an integer of their own numbering, while `runners/serve.py:company_id_matches()` requires a
   UUID and refuses anything else.
2. **"Can a partner post a payment at all?"** — their document specifies
   `POST /api/partner/v1/make-payment/`. Everything our partner surface serves today is a READ.
3. **"Can a partner waive a late fee?"** — their request body carries `late_fee_waived: true`.
4. **"Overpayment → credit note, on their say-so?"** — their request body carries
   `create_credit_note`.

### The FIFTH ruling, later the same day

**Not an answer to a question — an answer to an EXPLANATION.** Ruling 1 had been recorded, and the
Product Owner was then told in plain English that `company_id` SELECTS nothing (the key resolves
the utility and RLS does the isolating) but that **a mismatch is REFUSED today**, with a `403`.
They replied:

> *"you will ahve to remove company ID filter from all Apis - we cannot tell tenant ID outside our
> system"*

⚠ **THIS REVERSES RULING 1, AND ALSO THE 2026-09-16 RULING THAT PUT THE CHECK IN THE CODE.** The
full chain, what each was read as, and what was built from each, is in §2.

### And a NARROWING of ruling 2, also the same day

**Asked how the payment rows physically reach us**, the Product Owner answered:

> *"no this is not there - we will call htheir APis - we will ahnel those APis seperately - rember
> Invoice Cloud is both direction"*

⚠ **SO THERE IS NO FILE.** *"Batch run"* in ruling 2 means **we dial Invoice Cloud's own APIs on a
schedule and collect the payments** — a `fetch` operation going OUT. Not a file landing, not an
SFTP drop, not the remittance half of `lockbox.py`. **Ruling 2's substance is unchanged and is its
NEGATIVE half — no partner payment POST.** What was wrong was OUR reading of two words, and it is
corrected in §2 and §6 as dated clauses rather than by rewriting the ruling.

---

## 1 · Classify — two CHANGES, two CONFIRMATIONS, and one ruling superseded before it was built

`13-change-process.md` §1: *when it is ambiguous it is a DEFECT, not a change, because filing our
misunderstanding as a "change" quietly converts our error into the customer's new requirement.*

| # | Subject | Class | Why |
|---|---|---|---|
| 1 | `company_id` | ⚠ **SUPERSEDED by ruling 5, same day. NEVER BUILT** | It would have moved what `company_id_matches()` accepts. Recorded as made; it is not the agreement |
| 2 | Partner posting a payment | **CHANGE** — and the largest in this integration | A capability their document specifies is refused. ⚠ **NARROWED the same day:** the intake is a scheduled call to THEIR API, not a file |
| 3 | Late-fee waiver | **CONFIRMATION** | `BR-BIL-003` already says a waiver is a manual staff decision. The ruling says an outside system is not staff |
| 4 | Credit note on overpayment | **CHANGE** — narrow | `BR-PAY-010` sends an overpayment to account credit. A partner flag now reaches a different artefact |
| 5 | `company_id` removed from all APIs | **CHANGE** — and it REVERSES a built check | The `403` and check 7 come out. Isolation is untouched: `company_id` never isolated anything |

**Nothing here is a defect.** The product does what was agreed; a partner's document asked for
four things and the agreement has now answered each — and then moved once more on the first.

---

## 2 · What signed statement is reversed, with its chain

**No ❄️ FROZEN B4/B5 figure is touched.** Checked rather than assumed: `04-money-math-rules.md`
and `05-golden-tests.md` carry no partner, no `company_id`, no waiver flag and no credit-note
flag. No money math moves. Rounding, the four-decimal store and the allocation order are all
untouched.

### ⚠ Ruling 1 — SUPERSEDED BY RULING 5 THE SAME DAY, NEVER BUILT, KEPT AS RECORDED

> **Read ruling 5 below for the current law.** This section describes a comparison that is no
> longer in the agreement. It is kept rather than deleted because `serve.py`'s docstring still
> quotes the 2026-09-16 sentence this ruling superseded, and a reader tracing that quotation needs
> the middle link. **`BR-INT-070` carries the current law and the whole chain.**

**SUPERSEDED: the reading of PO ruling 2026-09-16, *"company_id = tenant id"*.** That sentence
was read as *the partner sends OUR uuid*, and `company_id_matches()` was built to it — it parses
the presented value as a `uuid.UUID` and returns `False` for anything that is not one. The 2026-09-17
ruling says the KEY is what guarantees the tenant and `company_id` only has to MAP to it.

⚠ **`BR-TEN-003` IS UNTOUCHED AND IS NOT WHAT MOVED.** *"The ONLY input consulted is the request
path; `tenant_id` in a header/param/body is never read"* — as narrowed 2026-09-16, a key is proof
and not a claim. The tenant still comes from the key, through
`key_directory.open_utility_for` in `partner_urls.py`. `company_id` is still **VERIFIED and never
used to SELECT**, a missing value is still a NO, and the refusal is still a `403 COMPANY_MISMATCH`.
**What changes is only the set of values that compare equal**, and nothing about who decides the
tenant.

### Ruling 2 refuses a capability their document specifies

**There is no signed statement to reverse, and that is worth stating plainly rather than leaving
to be inferred.** Grepped across the whole tree: **nothing in this repository promises that the
partner surface will accept a payment POST.** `partner_urls.py` mounts five addresses and all five
are `GET`. `ROUTE_WAVE` is empty. No manifest, epic, business rule or endpoint table commits us to
`POST /api/partner/v1/make-payment/`, and no lane is building one.

⚠ **AND THE RULING AGREES WITH THE SHAPE THE PRODUCT OWNER ALREADY DESCRIBED ON 2026-09-06**,
which is why this is a scope decision rather than a reversal. Verbatim, that day:

> *"In integration - for invoicecloud we have both. Cases together they hold ours and we hold
> theirs. **They will call our invoice and account APIs and we will call their payment APIs for
> payment records**. I hope we are handing both things together and for one integration there can
> be multiple endpoints/ spit to integrate or connect"*

Their side READS from us; our side CALLS THEM for payment records. The 2026-09-17 ruling names the
CADENCE of that second half — **a batch run, not online updates** — and refuses the third shape
their API reference introduced, which is them writing money into us live.

### ⚠ NARROWED THE SAME DAY — *"batch run"* is a SCHEDULED CALL TO THEIR API, not a file

> *"no this is not there - we will call htheir APis - we will ahnel those APis seperately - rember
> Invoice Cloud is both direction"*

**THERE IS NO FILE.** We dial their APIs on a schedule and collect the payments — a `fetch`
operation going OUT. **Not** a file landing, **not** an SFTP drop, **not** the remittance half of
`lockbox.py`.

⚠ **WHAT THE PRODUCT OWNER ACTUALLY RULED IS THE NEGATIVE, AND IT IS UNCHANGED:** no partner
payment POST, and **nothing a partner sends writes money the moment it arrives.** HOW the rows
reach us was never in their sentence — it was our reading of two words, and they corrected it the
same day, before anything was built.

⚠ **THE SEQUENCE IS KEPT VISIBLE ON PURPOSE.** Ruling 2 stands above exactly as the Product Owner
said it, and this is a dated clause underneath it. **A reader must be able to see that *"batch
run"* was first read as a file and then narrowed within hours** — smoothing that away is what costs
a later lane a week, and it is the same reasoning that leaves `CR-110-BRC04`'s worked `403` lines
standing under a note rather than rewritten.

⚠ **AND INVOICE CLOUD IS BOTH DIRECTIONS, IN THEIR OWN WORDS — THERE IS NO SECOND CONNECTOR.**
`manifests/pay_invoicecloud.py` is **EXTENDED**: it keeps its four card operations
(`deliver_charge` · `deliver_card_page` · `fetch_settlement` · `deliver_refund`) and its outbound
credentials, **gains the inbound-read half and `fetch_payment`**, and moves from `coming_soon` to
live. **This reverses an earlier recommendation of a second connector.** It is `DEF-INT-4118`'s
shape arriving for real — one relationship, two credentials pointing opposite ways — which the
execution plan already calls *"the best worked example"*, and the database's one-active-credential-
per-connection rule still has to accommodate it.

⚠ **ONE PIECE OF EXISTING TEXT COULD BE MISREAD AS A PROMISE AND IS ANNOTATED RATHER THAN
CORRECTED**, because correcting it would falsify a measurement.
`04-docs/05-modules/13-integrations/conformance/step0-vendors-20-28.md` records the Integration
Blueprint's own naming table, which draws `POST /partner/v1/payments`, `POST /partner/v1/payment-returns`
and `POST /partner/v1/delivery-receipts`. **Those are the KIOSK NETWORK's and the bulk-email
provider's, not Invoice Cloud's** — they are the `inbound_*` shape governed by `BR-INT-058`
(*they push: the door and the work are two separate acts*), ruled by `OQ-INT-1729` option (a) on
2026-09-06 and BUILT at a different address,
`POST /api/{utility}/integrations/inbound/{key}/{operation}` (`2.202.0`). **A signature covers
only what was shown**: the Product Owner was shown Invoice Cloud's `make-payment`, so this ruling
does not retire a door they ruled on a week earlier and were not asked about again. A dated note
is added beside that table so no lane reads a drawing of the kiosk's door as a licence to build a
partner payment POST.

### ⚠ Ruling 5 REVERSES ruling 1 AND the built check — `company_id` comes out of every partner API

> *"you will ahve to remove company ID filter from all Apis - we cannot tell tenant ID outside our
> system"*

**THE READING CHOSEN, four clauses:** the parameter is **NOT REQUIRED and NOT REFUSED** · it is
**STILL ACCEPTED and IGNORED**, because Invoice Cloud's own document sends it on every call and
refusing an unknown parameter would break a partner for no benefit · what they sent is **STILL
RECORDED ON THE RUN ROW**, so a manager can see *"this partner thinks we are 302"* without it being
a refusal — **which keeps the one genuine benefit of the old check, a misconfigured partner being
VISIBLE, at zero cost and with nothing exposed** · and **`403 company_id mismatch` DISAPPEARS FROM
EVERY PARTNER ROUTE**, taking `_admit`'s check 7 with it.

⚠ **ISOLATION IS UNTOUCHED, AND A LANE MUST NOT READ THIS AS THE DOOR GETTING LESS SAFE.**
`company_id` never isolated anything. **key → connection → tenant → `app.tenant_id` → RLS `FORCE`**
does, through `key_directory.open_utility_for` in `partner_urls.py`, and **that chain does not
move.** `BR-TEN-003` is untouched. This removes a cross-check, not a guard.

#### The supersession chain — three rulings on one parameter in eight days, the last two on one day

| | Date | Verbatim | Read as | Built? |
|---|---|---|---|---|
| **(i)** | 2026-09-16 | *"company_id = tenant id"* | the partner sends **OUR uuid** | **YES** — `company_id_matches()` parses a `uuid.UUID` and refuses anything else, and **quotes this sentence in its own docstring** |
| **(ii)** | 2026-09-17, ruling 1 | *"company_id = Keys will esnure it map to tenant ID"* | the partner sends **THEIR number**, compared against a value stored on the connection | **NO** — recorded, never built |
| **(iii)** | 2026-09-17, ruling 5 | *"you will ahve to remove company ID filter from all Apis"* | **no comparison at all** | **NOT YET** — the filter is still live and still refuses `403` |

**(iii) supersedes both (i) and (ii), and goes FURTHER than (ii) rather than restating it:** (ii)
kept a comparison, (iii) keeps none. **The reason is one neither of the first two considered** —
*we cannot tell tenant ID outside our system* — and it arrived only once the check's real behaviour
had been put in plain English. **(ii) was never built, so nothing is unwound. (i) IS built and is
what must be removed.**

⚠ **THE HONEST OBSERVATION, because it is the useful part.** This is not the Product Owner changing
their mind three times. **(i) and (ii) both answered *what should `company_id` be compared
against*, and neither of us had put the prior question — *should it be compared against anything at
all, given that a refusal tells an outsider something about our tenant*.** Said in plain English,
the answer came back in one sentence. That is law 13's plain-English rule earning its keep, and it
is also what asking the narrow question first cost: two rulings and a shipped check.

⚠ **`BR-INT-044` IS NOT AMENDED AND THIS MOVES IN ITS DIRECTION, NOT AGAINST IT.** Deleting the one
route-specific `403` leaves the refusal surface **simpler and harder to read anything out of**.
The six equalised auth refusals, their shared 41 bytes and their timing floor are untouched. **And
ruling 1's hazard — a new database read making a mismatch measurably slower than a match — cannot
arise, because there is no comparison left to make.**

#### ⚠ An open point for the build lane — FLAGGED, NOT DECIDED, and NOT put to the Product Owner

**Invoice Cloud's `consumer-info` RESPONSE carries `remote_utility_id: 393`.** If we cannot tell our
tenant id outside our system, **that field must echo THEIR number back, or be omitted — it must not
carry ours.** Nobody has raised this; none of the five rulings answers it. **Which of the two
answers is right is the building lane's call**, not a question for the Product Owner: it is a
consequence of a ruling they have already made.

#### What must move with the code, because the citations are the part that rots

Grepped, so this is a list and not a warning:

* `runners/serve.py:company_id_matches()` **and its docstring, which quotes ruling (i) verbatim**.
* `partner_api._admit` check 7 and its `403` — described in that function's own docstring as
  *"the ONE place a partner is told something specific"*.
* **Two docstring reasonings that are now VOID rather than merely stale:** *"`company_id` IS
  REQUIRED ON EVERY ROUTE AND NOT ONLY ON `reference`"*, and the hard-won-law-3 paragraph making a
  missing value a NO. Both argued for a check that is being removed.
* `06-backend/tests/test_us_int_041_partner_surface.py` TC-7b · `test_cr110_partner_tenant_from_key.py`.
* `EP-INT-11` TC-7 · journey `J54` step 12 · the worked `403 COMPANY_MISMATCH` lines in
  `CR-110-BRC04`. **These three are amended in the same commit as this file** — they are records.
* **`06-backend/openapi/schema.json` needs NOTHING** — grepped, **0 hits** for `company_id`, so the
  published specification never listed it.

⚠ **IT CHANGES THE PRODUCT OWNER'S OWN LIVE TESTING**, and they will meet it before any of us do:
today their Postman calls must carry `company_id`; after this they need not.

### Ruling 3 confirms `BR-BIL-003` and extends it by naming a new actor

`BR-BIL-003` (CONFIRMED, B4 §Late fee): *"First-time late-fee waiver is a manual staff decision,
never automatic."* It is written against a clerk and an automatic rule. **It never contemplated a
third party asserting a waiver in a feed**, so the ruling adds the actor rather than changing the
rule: an outside system is not staff, and `late_fee_waived` in their feed is not honoured.

### Ruling 4 narrows `BR-PAY-010`'s default, and only for a flagged row

`BR-PAY-010` and `BR-PAY-012` send an overpayment to **account credit** — `allocation.py` carries
it as `credit_carried` and never drops it. That stays the default and is what an unflagged row
still does. **The ruling adds one case:** where the partner's row carries `create_credit_note`, we
honour it.

---

## 3 · Impact

| Surface | Effect |
|---|---|
| `runners/serve.py` | ⚠ **RULING 5:** `company_id_matches()` is REMOVED. (Ruling 1 would have changed it; ruling 5 deletes it) |
| `partner_api.py` | ⚠ **RULING 5:** `_admit` check 7 is REMOVED, with its `403 COMPANY_MISMATCH` and the two docstring reasonings that argued for it. The door goes from nine checks to eight |
| `partner_urls.py` | **No new route.** The five addresses stay five, and all five stay `GET` |
| Connection config | ⚠ **NOTHING IS STORED.** Ruling 5 removes the comparison, so ruling 1's stored number is not needed and must not be added |
| Run row | What the partner SENT as `company_id` is recorded, so a misconfigured partner stays visible without being refused |
| `consumer-info` response | ⚠ **OPEN POINT:** `remote_utility_id` must echo THEIR number or be omitted — **never ours**. Flagged for the build lane, not decided |
| `apps/payments` | The feed reads `late_fee_waived` and does not honour it; reads `create_credit_note` and does honour it; flags the waiver row for a clerk. ⚠ **It is NOT the remittance import path** — no file, no `lockbox.py`, no `payment_import_batches` |
| `manifests/pay_invoicecloud.py` | ⚠ **EXTENDED, NOT REPLACED, AND NO SECOND CONNECTOR.** Keeps its four card operations and outbound credentials, gains the inbound-read half and `fetch_payment`, moves from `coming_soon` to live |
| Business rules | `BR-INT-070` · `BR-INT-071` (integrations) · `BR-PAY-1150` · `BR-PAY-1151` (payments) |
| Idempotency (hard rule 6) | ⚠ **AN OPEN GAP ON A MONEY PATH — `OQ-INT-12396`.** There is no file, so `payment_import_batches`' file-derived key does not reach this feed. See §6 |
| Open questions | **None closed and none opened by these four rulings.** No OPEN row in `01-open-questions.md` asks any of the four; grepped for `company_id`, `make-payment`, `late fee`/`waiv`, `credit note`/`overpay` and *partner payment* |
| `BR-TEN-003` | Untouched |
| `BR-INT-044` | Not amended. Ruling 5 moves in its direction — one fewer route-specific refusal |
| ❄️ B4 / B5 | Untouched. No frozen figure appears in any of the four subjects |
| Demo fixture | Unaffected |
| Screens | None. No clerk-facing screen changes on any of the five |
| The PO's own testing | Their Postman calls need no longer carry `company_id` |

### ⚠ `BR-INT-044` — the refusal must not start varying

`BR-INT-044` and the eight refusal codes of 2026-09-16 make every auth refusal **one refusal on
the wire**: the same 41 bytes, the same `404`, the same elapsed time, padded to a floor, proved
for all six causes side by side *on bytes, status AND elapsed time*. **A refusal that varies is a
timing oracle**, and this is the one clause a `company_id` change can breach by accident.

**Ruling 1 does not change the refusal, and the lane must keep it that way.** Stated explicitly so
it cannot be assumed:

* Check 7 is **not** an auth refusal and never was. It is `403 COMPANY_MISMATCH` — *the ONE place
  a partner is told something specific* — and it happens **after** checks 1–5 have already
  admitted the key. Nothing in the six-way equalisation is in play.
* **The danger is a new database read.** Today `company_id_matches()` reads `caller.tenant_id`,
  already in hand, and does no query. Comparing against a value **stored on the connection** must
  come from the row `resolve_caller` already loaded, **not from a second lookup** — a query here
  would make a mismatched `company_id` measurably slower than a matched one, which is `BR-INT-044`'s
  own oracle wearing the fix (the shape wave E recorded when it moved the run-row write inside the
  40ms padding).
* **A connection with no stored number must be a NO, not a pass.** Hard-won law 3: the unsafe
  option is the one you type. Absent must not be read as *the caller meant their own*.
* The comparison stays **case-folded after stripping**, as it is today, so a partner is not refused
  over a capital letter.

---

## 4 · What is already built, and is now in the wrong place

**Rulings 1 and 5 — one function, its caller, and four docstring paragraphs.** `company_id_matches()`
at `06-backend/apps/integrations/runners/serve.py:793`, its docstring (which quotes the 2026-09-16
reading verbatim), `partner_api._admit` check 7 and its `403`, and
`test_us_int_041_partner_surface.py`'s `TC-7b`. ⚠ **UNDER RULING 5 THIS IS A DELETION, NOT AN
AMENDMENT** — ruling 1 would have changed what the function accepts; ruling 5 removes the function.
**TC-7b is REWRITTEN, not deleted**: it must now assert that a wrong `company_id` is served
normally and that what was sent is recorded.

**Ruling 2 — nothing is built and nothing is wasted.** No route, no runner, no test and no
manifest operation exists for `make-payment`. The collision is with a partner's document, not with
our code, so no line is discarded.

**Ruling 3 and 4 — nothing is built.** The batch feed that would carry these two flags does not
exist yet. Both rulings land as rules the feed is built TO, which is the cheap direction.

**Lanes building right now** (change process step 4): three sibling lanes hold
`06-backend/apps/integrations/partner_api.py`, `expiry.py` and the Integrations tab in the shared
tree at the time of writing. **None of them is in `company_id_matches()` and none is building a
payment path.** Nobody needs to be stopped.

---

## 5 · Size, and the fast path

**Ruling 2 is the whole size of this CR, and it is a NEGATIVE size**: it removes a build rather
than commissioning one. `POST /api/partner/v1/make-payment/` is not built — no route, no
idempotency design for a live inbound money write, no refusal ladder, no per-call money audit.
Against the shape of the five `GET` routes already built, that is the largest single item the
Invoice Cloud integration would have carried.

**Ruling 5 is a DELETION and takes the fast path** — one function removed, one check removed from
`_admit`, four docstring paragraphs removed, two test rows rewritten, one record line each in the
epic and the journey. It touches a money-adjacent door but no money math, no rule and no stored
money value, and it makes the door smaller. **Ruling 1 is not built at all**, so its size is zero.

**Rulings 3 and 4 commission nothing today.** They are rules the payment-feed batch is built to
when it is built, and they are recorded now precisely so it is not built the wrong way first.

### What is deliberately NOT decided here, and is the building lane's

Law 13: *a judgment call recorded in the decision log with its reasoning is the deliverable; a
question is the failure to make one.* None of the following is put to the Product Owner.

* **What `remote_utility_id` carries in the `consumer-info` RESPONSE** — THEIR number echoed back,
  or the field omitted. **Never ours.** Ours to choose; flagged in §2 under ruling 5.
* ⚠ **Ruling 1's *where do we store their number* is VOID** — ruling 5 removes the comparison, so
  nothing is stored and no field is added. Recorded so a lane that read ruling 1 first does not
  build it.
* **The cadence — ⚠ PARTLY ANSWERED BY THE NARROWING, AND STILL OPEN.** `BR-INT-057` gives three
  triggers (scheduled · one-off · their call). Ruling 2 rules out *their call*, and the narrowing
  settles that it is a **schedule** whose trigger fires an **outbound call**. **At what hour, and
  whether a tenant sets it, is still ours** and still belongs in the tenant's settings rather than
  in a manifest (`BR-INT-056`: *no time of day on a connector*).
* ⚠ **NOT ours, and NOT the Product Owner's: `OQ-INT-12396`**, the idempotency key for a scheduled
  pull. Routed to Invoice Cloud, because only their API can say what is stable and unique.
* **Which screen shows a flagged waiver row.** Ours.

---

## 6 · Hard rule 6 on this path — what exists, what does NOT reach it, and the open gap

⚠ **READ THIS FIRST. THE VERIFICATION BELOW IS A RECORD OF WHAT EXISTS AND IS NO LONGER THIS
FEED'S IDEMPOTENCY.** When it was written, *"batch run"* was read as a file arriving. The Product
Owner narrowed that the same day — *"we will call htheir APis"* — so **there is no file, and every
part of `payment_import_batches`' key is derived from one**: `file_hash` is *"SHA-256 hex of the
exact bytes uploaded"*, and on a scheduled outbound pull there are no bytes to hash. **That
machinery stays exactly as it is and stays correct for the bank and lockbox families it was built
for. It is simply not this feed's guard.**

### ⚠ So the idempotency for this feed is an OPEN DESIGN POINT on a money path — `OQ-INT-12396`

**Filed rather than implied, because a gap nobody can see is a gap nobody closes.** Hard rule 6
applies to a scheduled pull exactly as it applies to every other inbound payment. **A re-run, a
collection that times out half way, or a window re-run over an overlapping date range can present
the same payment twice — and nothing in this product would currently refuse the second one.**

What their API gives us to key on is the fact we do not have: their own payment id, a **composite**
(the shape `BR-INT-058` already met with the kiosk, whose *"id alone is not a sufficient key: a
reversal carries the same one as the payment it reverses"*), or a settlement identifier bracketing
a set. **That is a fact only Invoice Cloud can supply**, so it is routed to them on `OQ-INT-1476`'s
precedent rather than put to the Product Owner, and **it is not guessed: a guess here is a customer
paying twice.**

**The collection may be built and may be scheduled. Nothing may WRITE a payment from
`fetch_payment` until `OQ-INT-12396` is answered.**

### The verification itself, kept for the record

The briefing for this record asserted that the existing machinery already carries idempotency for
a batch feed. **It was checked against the code before being written down**, and it holds **as a
description of the FILE families** — which, after the narrowing, this feed is not one of.

* **The unique key exists and is scoped as claimed.** `apps/payments/models.py:1165`:
  `UniqueConstraint(fields=["tenant", "file_hash", "tag_fingerprint"], condition=Q(status=IMPORT_COMMITTED,
  file_hash__isnull=False), name="uq_payment_import_batches_idempotency")`. **Scoped to COMMITTED
  batches on purpose** — the model's own comment says `OQ-044`'s closure blocks the COMMIT and not
  the staging, so a clerk may re-open the modal on the same file all morning and only a second
  COMMIT is refused. `file_hash` is *"SHA-256 hex of the exact bytes uploaded — computed
  server-side, never accepted from a client"*, so one changed row is a different file and a
  corrected re-send imports normally.
* **`lockbox.py` is the one parser, and this was verified by its callers rather than by its
  docstring.** `parse_remittance_file` has exactly one production caller —
  `payment_import.py:371` — and `parse_bank_statement` exactly one, `reconciliation.py:1162`.
  `payment_import.py` also takes `file_sha256` and `remittance_tag_fingerprint` from it, so the
  hash, the tag half of the key and the parse all come from the same module.
* ⚠ **THE CORRECTION: `lockbox.py` SERVES TWO FAMILIES AND THEY ARE DIFFERENT DIRECTIONS OF
  MONEY.** Its own docstring falsifies an earlier claim about itself and says so: the **bank
  statement** half (`US-PAY-021`, S38) stamps `bankrec_models.BankStatementImport`, and the
  **remittance** half (`US-PAY-003`, `BR-PAY-023`) stamps `payment_import_batches` and is the one
  that CREATES payments. **A partner payment feed is the remittance family**, so
  `payment_import_batches` is the right table and the constraint above is the right key. A lane
  that reads only the trace header will find `file_hash + tag_fingerprint` named against
  `BankStatementImport` and reach for the wrong one.
* **So hard rule 6 needs no new mechanism for this feed** — it needs the feed routed through
  `payment_import`, which is `BR-PAY-023`'s staged-import pattern, and not through a new path.

---

## 6b · RULED 2026-09-17 · TWO CONNECTORS, AND WHAT THE SECOND HALF OF THE RULING OWES

**The blocker.** Everything this CR shipped at `2.289.0` was unreachable. A key is issued only
where a manifest reads `they_hold_ours`; `pay_invoicecloud` reads `we_hold_theirs`, because we dial
them to charge a card. One connector, one direction, and Invoice Cloud runs in two
(`DEF-INT-5574`). Three ways out were put to the Product Owner in plain English.

**The ruling, verbatim.** *"a) Two connectors — one for the reading half, live now; the card one
stays where it is	the customer gets their key today. Two rows in the list with the same company
name - this is correct - we ahve to issue our key and also save secrete given by them in bi
directional Connectors"*.

⚠ **THE SECOND SENTENCE IS A REQUIREMENT, NOT A DESCRIPTION.** One connector holding BOTH
credentials is what they want and what the product cannot express. **Two rows is an accommodation
of a product limitation and is not the target shape** — `BR-INT-077` records what is owed, and it
is a separate change with its own CR. `DEF-INT-5574` is closed **partially-fixed** for exactly that
reason: the symptom is gone, the cause stands.

**Built:** `manifests/pay_invoicecloud_partner.py` — the twenty-ninth connector, `payments`,
`live`, `they_hold_ours`, `allowed_addresses` (optional) + `issued_key`, and four operations:
`serve_customer` · `serve_bill` · `serve_payment` · `serve_document`, at 60 · 60 · 60 · **600** a
minute. One file and one name in `manifests/__init__.py`; no table, no column, no migration, no
screen code.

**`serve_document` closes `DEF-INT-5586`** — `bill-download` had been registered, routed and
unreachable by every key that could exist. Proved live: `200 application/pdf · 6,311 bytes ·
"%PDF-1.4"`.

**No `fetch_payment`**, and that is `BR-INT-071`'s own refusal being obeyed: `OQ-INT-12396` is OPEN
and we do not hold their API specification, so the operation is not declared rather than declared
and unusable.

**`pay_invoicecloud` is untouched** — four card operations, `we_hold_theirs`, `coming_soon · W7`,
connect still refused `409 BR-INT-001` on the running product.

**`BR-INT-071` amended.** Its clause *"there is no second connector … `pay_invoicecloud` is
EXTENDED"* was a reading of *"rember Invoice Cloud is both direction"* and was not buildable; it is
stamped SUPERSEDED in place, with the ruling that superseded it quoted beside it. The rest of that
rule — no partner payment POST, nothing writes money on arrival — is untouched.

## 7 · Version

**`2.291.0`**, allocated through `10-scripts/allocate.py version --bump change` against the remote
(never this checkout — `DEF-GOV-3756` is two lanes shipping the same number). Written in all three
literals: `07-frontend/package.json`, `07-frontend/package-lock.json`, `06-backend/pyproject.toml`.

## 8 · Rollback

**Section 6b ships code; everything before it is a document row.** Rolling 6b back is deleting
`manifests/pay_invoicecloud_partner.py` and its name in `manifests/__init__.py`, and moving four
counts back — 29 → 28, `they_hold_ours` 7 → 6, the catalogue 383 → 375 — which is the whole of it,
because a connector is data. **No migration runs and none is reverted.** ⚠ **What a rollback DOES
cost is live:** any key a utility has issued on that connector stops resolving, because the
manifest it points at no longer loads, and a key is shown once and cannot be recovered — so a
rollback is a re-issue for every utility that has connected. **Everything before section 6b is a
document row.** Rolling those back is reverting one commit; no database is written, no route is
mounted and no behaviour changes. The rulings themselves cannot be
rolled back by us — they are the Product Owner's, and a reversal would be a new change request.
