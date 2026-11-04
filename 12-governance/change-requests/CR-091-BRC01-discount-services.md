# CR-091-BRC01 — A discount names ONE OR MORE utility services, and the screens show and edit them

**Raised:** 2026-09-10 · **Requester:** the Product Owner, in the working chat session
**Branch block:** `BRC01` (`claude/hi-0jmv62`) · **Module:** rating · **Status:** CAPTURED, not sized

---

## 0 · CAPTURE — the requester's words, verbatim

> *"Also please note when we create discount - we will ahve to take 1 or more
> utility services - currently it is not available. also we will ahve to dsplay
> in detail view and also allow to enit it duing edit process - please capture
> this into your changes"*

Three asks in one sentence, and they are three different surfaces: **create**,
**read**, **edit**.

---

## 1 · CLASSIFY — a CHANGE, and the test is the one in the process

*Can a user do this task in the product today?* **No.** So this is BUILD, and it
is a change request rather than a defect: nothing was specified and then missed,
the capability was never asked for until now.

⚠ **IT IS NOT "the service picker is missing" — THERE IS ONE, AND IT IS
SINGULAR.** That distinction decides the size of the work, so it is written out
rather than left to be discovered:

| where | what exists today | evidence |
|---|---|---|
| the scope choice | five values — `whole_bill`, `one_service`, `usage_only`, `base_only`, `named_codes` | `endpoints.ts:4229-4235` |
| the control | a **single-select**, shown only when the scope is `one_service` | `DiscountWizard.tsx:1176-1186` |
| what is stored | `applies_to_service` — **one** service | `discount_services.py:108`, `:312` |
| what prices the bill | `[line for line in lines if line.service == rule.applies_to_service]` — an **equality** | `discount_pricing.py:316` |
| the detail view | **nothing at all** — no service is displayed on a discount | no `service` read in `definitionDetail.tsx`'s discount blocks |
| the edit path | the wizard's own control, so single again | — |

**So all three asks are real, and the third is not a variation of the first.**

⚠ **AND THE ENUM VALUE ITSELF ENCODES THE SINGULAR.** The scope is literally
named `one_service`. Widening it is therefore not only a column change — either
that value's meaning changes under a name that then lies, or a new value joins
it. That is a decision, and it is in §5.

---

## 2 · WHAT SIGNED STATEMENT IS BEING REVERSED

**None found.** No business rule states that a discount applies to at most one
service; the singular appears to be an implementation choice that was never
ruled either way. **This is stated as a search result, not as a certainty** —
whoever sizes this re-greps `04-docs/05-modules/06-rating/02-business-rules.md`
for `applies_to_service` and `one_service` before relying on it.

⚠ **THE PRECEDENT IS IN THE SAME FILE AND IT IS PLURAL.** A **tax** already
carries `applies_to_services` — *"a JSON list of catalog codes"*
(`models.py:913`) — validated against the tenant's enabled services, served on
two selectors (`:828`, `:2840`). So the product already knows how to hold this
shape for a sibling object, and the discount is the odd one out. Anyone building
this should copy the tax's column, its validation and its serialisation rather
than inventing a second spelling.

---

## 3 · IMPACT — where this lands

| surface | what changes |
|---|---|
| **schema** | a plural column on the discount, plus a migration. The tax's `applies_to_services` JSON list is the shape to copy |
| **pricing** 🔒 | `discount_pricing.py:316` moves from `==` to membership. **This is money math and is a 🔒 sensitive path** |
| **write path** | `discount_services.py` validation — a list, each code against the tenant's enabled services (the tax already does exactly this) |
| **create screen** | `SelectField` → the kit's `ChipMultiSelect`. B14 rule 9 requires chips for a multi-select and forbids a wall of checkboxes |
| **detail view** | a new field in the discount's blocks — **it shows nothing today** |
| **edit** | follows the create control once it is plural |
| **the scope enum** | see §5 — a decision, not a mechanical change |
| **data already written** | every existing discount holds at most one service. A migration must carry it into the list rather than dropping it |
| **eleven catalogues** | a label, a help line and an empty state, in all eleven, via `10-scripts/i18n_fanin.py` |

⚠ **AND IT COLLIDES WITH `CR-087`'s DISCOUNT WIZARD WORK, WHICH IS LIVE.** The
conformance pass has just documented that same step and the fix wave has not
started. Whoever builds this must read
`04-docs/05-modules/06-rating/conformance/CR-087-p065-*.md` first, or the two
changes will fight over one control.

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

Nothing shipped becomes *wrong*; it becomes *narrow*. But two things are worth
naming so nobody reports them as fresh defects afterwards:

* the drawn blueprint frame for this step shows a **single** service, so the
  drawing is now behind this ruling and must be amended rather than followed;
* `rating.discountWizard.serviceHelp` and `rating.filter.service` are written in
  the singular in all eleven catalogues.

---

## 5 · WHAT THE PRODUCT OWNER STILL HAS TO SETTLE

Captured, not decided. Each changes the build.

1. ⚠ **ANSWERED — PO 2026-09-10: A NEW CHOICE JOINS, AND THE PAIR IS NAMED.**
   Verbatim: *"Add a new choice. - one or more services from drop down; All
   services or sepecific services; this is correct"*.

   **So the clerk is offered a PAIR — `All services` or `Specific services` —
   and choosing the second opens a dropdown that takes one or more.** `one_service`
   is not widened: every discount already saved keeps exactly the meaning it had,
   and no migration has to reinterpret stored rows.

   ⚠ **AND THE PAIR SETTLES QUESTION 2 BELOW MORE CLEANLY THAN THE ANSWER
   PROPOSED FOR IT.** The recommendation put to the PO was *an empty list means
   every service*, copied from how a tax behaves. With `All services` on screen
   as its own choice, an empty list stops being an expression of intent and
   becomes an **unfinished form**: a clerk who meant every service says so, so
   `Specific services` with none chosen is a REFUSAL, not a synonym. That is
   both safer and what the screen now looks like.
2. ⚠ **ANSWERED BY CONSEQUENCE OF 1, above — an empty list is REFUSED.** Once
   `All services` is a choice a clerk can make, `Specific services` with nothing
   chosen means the form is not finished. **Do not copy the tax's `NULL or []`
   means everywhere reading here**: the tax has no such pair on screen, so its
   empty list carries meaning it cannot carry once the pair exists.
3. **May a discount name a service the plan does not sell?** The tax validates
   against the tenant's enabled list; a discount could reasonably be stricter
   and validate against the plan's.

---

## 6 · STATUS

⚠ **PO RULING 2026-09-10 — BUILT INSIDE `CR-087`, NOT AS A SEPARATE WAVE.**
Verbatim: *"CR-091-BRC01. - implemnt it during the CR 87 itself - not
sperately"*.

**So this CR is the SPECIFICATION and `CR-087`'s discount fix wave is the
VEHICLE.** It keeps its own number because the requirement is its own — it was
raised separately, it reverses nothing in `CR-087`, and a reader asking *"where
did per-service discounts come from"* needs to land here. What it does not get
is its own wave, its own version bump or its own close-out.

**What that decides, and it is the reason the ruling is the right one:** the
discount wizard's service control is a screen `CR-087`'s conformance pass has
just documented and whose fix has not started. Two waves touching one control
would collide, and the second would be rebuilding the first's work. The lane
that re-cuts that step now builds it PLURAL in the same pass, rather than
building it singular to match the drawing and widening it a day later.

⚠ **AND IT MOVES THE THREE QUESTIONS IN §5 ONTO `CR-087`'s CRITICAL PATH.**
They were *"settle before building"* when this was a separate wave; they are now
*"settle before the discount fix lane starts"*, which is sooner. They are listed
in the `CR-087` decision table put to the PO on 2026-09-10.

⚠ **BUILT 2026-09-10, INSIDE `CR-087`'s DISCOUNTS FIX WAVE, EXACTLY AS THE
RULING ABOVE DIRECTED.** All three asks are live:

| the ask | where it landed |
|---|---|
| **create** — take one or more services | the scope gains `all_services` and
`specific_services`; the second opens the kit's `ChipMultiSelect`
(`DiscountWizard.tsx`, step 2) |
| **read** — show them on the detail view | a `Services` row in *what it is
worth*, always drawn, reading `All services` where nothing narrows
(`definitionDetail.presentDiscount`) |
| **edit** — change them on the edit door | `draftFromDiscount` round-trips the
list and the edit door posts it |

**§5's three questions are all answered.** 1 and 2 by the PO on 2026-09-10
(the pair, and an empty list REFUSED). **3 — *may a discount name a service
the plan does not sell?* — is answered the tax's way**: validated against the
TENANT's enabled services, not the plan's, because that is the precedent §2
names and a stricter rule would refuse a discount written before the plan
that carries it. Recorded as a judgment rather than re-asked (law 13).

⚠ **AND §4's TWO WARNINGS BOTH HELD.** The drawn frame shows a SINGLE
service and is now behind the ruling — recorded as a divergence in
`CR-087-p067` rather than followed. `rating.discountWizard.serviceHelp` and
`rating.filter.service` keep their singular wording and are still correct:
they belong to the `one_service` control, which is untouched.

**Status: BUILT · rules `BR-RAT-963` · 🔒 HUMAN-REVIEW-PENDING** (rating math
and migration ordering — row in `12-governance/09-human-review-ledger.md`).

---

## Trace
- raised 2026-09-10 by the PO in the working chat session
- captured the same turn, per hard-won law 9 — the conversation does not survive, the repo does
- number taken from the `BRC01` block after `10-scripts/allocate.py cr --verify 90`
  reported `CR-090` **TAKEN by a sibling**; see `14-id-reservations.md`
