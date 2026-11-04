# `CR-122-BRC06` · A move-in carries the request it came from — its details AND its documents

| | |
|---|---|
| Raised | 2026-09-19, in the working chat session, while the PO read the move-in wizard against blueprint pages 067–073 |
| Requester | Product Owner |
| Branch | `claude/kind-wozniak-rl0uzt` · block `CR-120`–`CR-124`, suffix `BRC06` |
| Module | customers |
| Classification | **CHANGE** — argued in §1, not assumed |
| Version | `2.311.5` at capture |
| Status | **CAPTURED 2026-09-19 · not sized with the PO yet** |
| ⚠ Read first | **THE COLUMN ALREADY EXISTS.** `service_request_id` joined `MOVE_IN_FIELDS` on 2026-09-15 and the server accepts it. The front end has never set it or read it. This is a wiring change wearing the costume of a feature. |

---

## 0 · Capture — the requester's words, verbatim

Two sentences, given minutes apart while reading step 2:

> *"at this stage Customer - you also need to allow to submit document - similar to what we did
> in new reeust. even drawing dont show it right now"*

> *"here if ove is coming from service request these details will be filled in"*

**They were given as two asks and they are one change**, which is why they are captured in one
CR rather than two: the documents a move-in needs are the documents its request already holds,
and the details it should stop asking for are the details that request already carries.

## 1 · Classification — CHANGE, and the argument for it

`13-change-process.md` §1 says an ambiguous item is a **DEFECT**, because filing our own
misunderstanding as a "change" converts our error into the customer's new requirement. So the
test has to be answered rather than waved through, and it splits:

* **The documents half is a CHANGE.** The PO said so themselves — *"even drawing dont show it
  right now"*. Blueprint page 068 draws step 2 with eleven fields and no document control, and
  no signed rule asks for one. The product is not failing to do what was specified; the
  specification is being extended. **Under B14 rule 41 the product matches the blueprint, and a
  PO instruction moves the blueprint — that is the one thing rule 41 is not about.**
* **The prefill half is nearer a DEFECT and is recorded as part of this change anyway.**
  `service_request_id` was added to the move-in payload on 2026-09-15 for exactly this purpose
  and nothing ever called it. That is hard-won law 2 — built and not wired — and on its own it
  would be a defect row. It is carried here because the two are one piece of work and splitting
  them would have two lanes touching one wizard.

## 2 · What signed statement is being reversed

**None.** No rule says a move-in may not take a document, and none says it may not read its
request. What moves is the DRAWING, on the PO's own instruction, and the divergence is recorded
in `04-docs/05-modules/03-customers/conformance/move-in-wizard-against-its-blueprint.md` so the
next lane meets the ruling rather than reading the drawing and "correcting" it back.

## 3 · Impact

| Surface | What changes |
|---|---|
| Move-in step 2 | a document control, and the fields arrive filled when a request is named |
| Move-in step 6 | the review reads the documents back with the rest |
| `service_request_id` | finally set, and read |
| The document store | **see §5 — the answer is probably "no new store at all"** |
| Request detail | approving a move-in request should offer the move-in, carrying its id |
| Move-ins tab | a move-in that came from a request should say so |
| Open questions | none minted — nothing here is a fact only the PO holds (law 13) |
| Demo fixture | a seeded request that became a move-in would exercise it |

## 4 · What is already built and is now wrong

**Nothing is wrong. Two things are idle.**

* `service_request_id` on the move-in payload — accepted, never sent.
* The document store landed 2026-09-19 (`678c49738`, `789f9ad7e`): a real store, shrinking on
  the way in with no pixel altered, tenant-scoped reads, bytes proved back out. It is scoped to
  a service request by foreign key.

⚠ **No lane is in `MoveInWizard.tsx` right now.** Two are live in the request screens
(`ServiceRequestDetailPage.tsx`, `ServiceRequestCapturePage.tsx`), so this does not collide —
but it will read the same document code, and it must not start before those land.

## 5 · The design question this change turns on, stated rather than buried

The store is `service_request_documents`, owned by a service request. A move-in is not one. So:

| | | |
|---|---|---|
| **a** | **The move-in carries its request, and the documents ride along** | **Recommended.** No new table, no second owner, no migration. A move-in that came from a request shows that request's documents; a move-in started from an account shows none, which is the honest answer |
| b | Generalise the owner — a nullable second foreign key, or a polymorphic owner | A migration on a store that is two days old, to solve a case option (a) already covers |
| c | A second table for move-in documents | Two stores for one idea; they will drift |

**Option (a) makes the change SMALLER than what was asked for**, and it falls straight out of
the PO's own second sentence. The one thing it does not cover is a move-in started from scratch
that needs a document; if that turns out to be real, (b) is the answer and it is a later change.

## 6 · Execute — through `r11`, unchanged

Not started. It queues behind the two live request lanes.

## 7 · Version

To be allocated with `10-scripts/allocate.py version --bump change` at build time.

## 8 · Close, and the rollback stated before shipping

Rollback is a front-end revert: the document control and the prefill are additive, `option (a)`
writes no new table, and `service_request_id` is already nullable. Nothing already stored
changes shape.
