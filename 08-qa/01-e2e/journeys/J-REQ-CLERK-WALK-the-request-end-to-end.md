# J-REQ-CLERK-WALK — a clerk takes a request end to end: draft, submit, open, and the four decisions

---
id: JREQCLERK
tier: 1
rules: [BR-CUS-090, BR-CUS-092, BR-CUS-094, BR-CUS-1020, BR-CUS-1022, BR-CUS-1070, BR-CUS-1077]
stories: [US-CUS-003]
# ⚠ **THIS IS A COMMITMENT, NOT A DESIGN.** The Product Owner specified this walk on
# 2026-09-19 and then asked, in as many words, that it be remembered and actually run.
# It is written here rather than left in a chat window because a commitment that lives
# only in a conversation is the context leak hard-won law 10 exists to stop.
# ⚠ **ACTIVATED AND RUN — 2026-09-19, at branch tip `412eb97b1`, v2.311.5.** The
# precondition this line used to state ("three lanes are live in the two screens this
# walk covers and the tree does not typecheck") is closed: the tip typechecks clean and
# the two screens have landed. `10-scripts/po20260919_clerk_walk_end_to_end.mjs` is the
# walk, `…_readback.py` reads every verdict back out of PostgreSQL, `…_purge.py` removes
# what it made. Result: **20 PASS / 5 FAIL on screen, 35 PASS / 5 FAIL in the database.**
# ⚠ **AND IT WAS PROVED CAPABLE OF FAILING BEFORE IT WAS BELIEVED (hard-won law 7):** the
# same script against a build of `5b0220ea3` (four hours older) scores **15 PASS / 10
# FAIL** — the four document-attach checks and the approve check go red there and green
# here, which is the attach work and the Approve dialog's `Record that I searched`
# landing in between. A walk first seen green is a walk nobody has proved.
---

## Why this walk exists, in the PO's own words

> *"when these screens are updated new request and detail view - i want you to do the walk -
> check how clark will do it - we need to remove any frictions for clark - so that theya re
> bale to execute this workflow in a simple way end to end and it does what it suppose to do"*

And then, precisely:

> *"baiscally you create requestwith all details -> save as a draft, and submit it - tow
> cases - see whther it behave correctly; then submitted request - open it see all the
> details - then 4 actions refuse, park, ask for more and apporve - whether it behave
> correctly"*

**The deliverable is not a pass/fail report. It is one list: what a clerk has to do that they
should not have to.**

## When it runs

**Twice, and the second run is the point.**

1. **BEFORE** — against the product as it stands, to establish the baseline and to prove the
   walk is capable of failing. A walk first seen green is a walk nobody has proved
   (hard-won law 7).
2. **AFTER** — against the same build once the request capture, the request detail and the
   document lanes have all landed. **The difference between the two runs is the report.**

## Case 1 · Fill in every field, SAVE AS DRAFT

| # | Check | Why it is here |
|---|---|---|
| 1.1 | A number is allocated **the moment the draft starts**, not at submit | The blueprint is explicit: *"a draft carries its number from the moment it is started. The clerk can quote it to somebody still standing at the counter"* |
| 1.2 | State reads **Draft** | |
| 1.3 | **Close the wizard, reopen it — every field of all six steps is still there** | Not asserted against component state. Closed and reopened cold |
| 1.4 | The draft is in the register | |
| 1.5 | A document attached on the draft survives, and its **bytes are still fetchable** | A row that comes back without its file is `DEF-CUS-5872`'s shape |
| 1.6 | **Nothing left the building** — no email, no account, no job, no money posted, no journal line | A draft is a draft |

## Case 2 · Fill in every field, SUBMIT

| # | Check |
|---|---|
| 2.1 | State reads **Submitted** |
| 2.2 | In the register, with the right **waiting-on** |
| 2.3 | **The applicant is told** — PO asked for this on 2026-09-17, *"now email is configured hence we can sent email now or notications"* |
| 2.4 | Any document attached is really stored and really comes back |
| 2.5 | Any fee taken is in **payments** and in **the books** |

## Then OPEN it — the check nothing else in this repository makes

**Every field captured across the six steps must appear on the detail page, one by one.**

A field a clerk types that the screen never shows again is silently lost: the clerk has no way
to know, and **no test here would go red for it**. The detail page is being cut down hard —
cards folded together, rows deleted, copy stripped under the PO's own copy ruling — which is
precisely when a captured fact falls off the page unnoticed.

Walk step 1 through step 6, list what each asks for, and find each one on the detail page.

## Then the four actions, one at a time

| Action | Must do | Must NOT do |
|---|---|---|
| **Approve** | Approved · the build is raised · any money owed travels with it | open an account · fit a meter · energise anything |
| **Refuse** | Refused · a reason is required · the applicant is told | **give the money back** — PO ruled 2026-09-15, *"if it is refuse then it is application fees non refundable - it stya in books"* |
| **Ask for more** | More info · waiting-on moves to the applicant · a message is sent | leave it looking refused |
| **Park** | waiting-on is set · **Submitted becomes Under review** | move anything else |

⚠ **EACH ONE VERIFIED IN THE DATABASE AFTERWARDS, NOT ON THE SCREEN.** A screen that says
*Approved* over a row that did not move is exactly the class of defect that only surfaces in
front of a customer.

## How to run it

A `.mjs` walkthrough in `10-scripts/`, the way ~80 siblings already do it — a real browser, a
real backend, real PostgreSQL, reading every figure back out of the database afterwards. Put a
hard timeout on every background job and close the browser in a `finally` (`DEF-GOV-5877`).
Leave the beta as it was found: count the service requests before and after, and purge by a tag.


## What it found — 2026-09-19, the first run

**Six defects, all filed:** `DEF-CUS-5902` (the connection date is replaced on the
detail page by the false sentence *"Different days per service"* — a REGRESSION: the
older build showed the date) · `DEF-CUS-5903` (the customer category is required,
stored, served, and rendered by no tab) · `DEF-CUS-5904` (no clerk can raise an
application fee anywhere, so the whole fee path is a dead end) · `DEF-CUS-5905` (step 6
prints a raw catalogue key) · `DEF-CUS-5906` (Ask for more never sets `waiting_on`) ·
`DEF-CUS-5907` (*What it proves* has no column on the detail page).

**Two already-filed defects confirmed live:** `DEF-CUS-5880` (reopening a saved draft
shows an EMPTY wizard — 12 fields came back blank) and `DEF-CUS-5881` (there is no way
to reopen a draft from any screen; this walk had to type the URL).

**What behaved correctly, read out of the database:** a draft leaks nothing — no
message, no fee, no account, no payment, no journal line; an attached document survives
with its bytes; Park moves `submitted` → `under_review` and sets `waiting_on`; Refuse
records a reason, tells the applicant and **does not give the money back** (the PO's
ruling of 2026-09-15); Approve reaches `approved`, carries its outcome, raises a
`move_in_jobs` row naming the request, and opens no account.

⚠ **TWO OF THE FOUR ACTIONS WERE MIS-DRIVEN ON THE FIRST RUN AND LOOKED BROKEN.** Park
and Ask for more both left the row unmoved — because the script pressed a generic
`^(Park|Save|Confirm)$` when the real buttons read `Park ✓` and `Ask and queue the
message`, and filled a `select` where `waiting_on` is a text field. Approve looked
permanently greyed for the same reason: the outcome is a RADIO, the first radio is
`new_connection` which the server grades `not_possible` on a served premises, and the
footer only enables after `Record that I searched` is pressed inside the dialog. **All
three were the walk's fault, not the product's, and each would have been filed as a
false defect.** Drive every dialog by its real control ids and its real submit label,
and record whether the fill actually took.
