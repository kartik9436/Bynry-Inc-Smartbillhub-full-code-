# EP-FLD-06 — Closing — signature, the four outcomes, reopen and what comes back

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 7 · **Design tasks:** T-21 · **Screens:** FF-33, FF-34, FF-35, FF-36, FF-37 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *FF-32 to FF-36* and the requirements whose screens sit in it — US-FLD-014 (requirement 14), US-FLD-024 (requirement 24).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| FF-35 Completed | customer | date range (Today · This week) · outcome | not declared | not declared | card: outcome, time, customer, address, number + type + labour, acceptance | Reopen · Raise follow-on / reconnect | — | — |

*Not declared* means the design does not say; requirement 37 and R44 require it declared and wired before the screen ships — the build lane declares it, it is not guessed here.

## Stories

---
id: US-FLD-014
epic: EP-FLD-06
module: field-app
screens: [FF-33, FF-34]
wave: 7
status: ready
blocked_by: []
depends_on: [US-FLD-008]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00030]
golden_tests: []
finance_calc: none
---
### US-FLD-014 — Customer signature, or a recorded refusal

**Requirement 14, in the design's words:** *Customer signature, or a recorded refusal — printed name plus image with who captured it and when. A refusal records the decline reason and a photograph of the door hanger* — section B · Found in the repo, missing from the brief · standing *Ruled*.

**1 · Details** — As **Dana closing WO-4822**, I want **the customer to sign with a printed name, or the refusal recorded with a reason and a door-hanger photo**, so that **the close carries proof either way** (R30, `BR-WRK-046`). On a tablet this is the one screen a tablet is simply right for — you hand it over.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-33` Signature — [phone](../wireframes/phone/FF-33-signature.png) · [tablet](../wireframes/tablet/FF-33-T-signature.png)<br>`FF-34` Close — [phone](../wireframes/phone/FF-34-close.png) · [tablet](../wireframes/tablet/FF-34-T-close.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00030` | R30 | A customer signature is a printed name plus an image, with who captured it and when. | CONFIRMED — repo `BR-WRK-046` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Sarah Miller prints her name and signs | *Captured by D. Ortiz · 20 Oct 09:58* |
| TC-2 | E2E-24: the customer declines; reason *Customer declined*; door hanger photographed | A refusal is a recorded outcome |
| TC-3 · **negative** | Refused with no door-hanger photo | Not saved — the photo is required on a refusal |
| TC-4 · **negative** | Signed with no printed name | Not saved |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Reasons: Nobody home · Customer declined · Tenant could not sign.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| signature | FF-33 | R30 | outbox `signature` + photo file | image + name | user-input | who and when stamped |
| refusal | FF-33 | R30 | outbox `signature` (refused, reason) + door-hanger photo | choice + photo | user-input | photo required |

**6 · Acceptance** — **Given** a job ready to close, **when** the customer signs or refuses, **then** either a signature or a refusal with its reason and photo is recorded.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-024
epic: EP-FLD-06
module: field-app
screens: [FF-35, FF-36, FF-37]
wave: 7
status: ready
blocked_by: []
depends_on: [US-FLD-008, US-FLD-011]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00021, BR-FLD-00022, BR-FLD-00023, BR-FLD-00024]
golden_tests: []
finance_calc: none
---
### US-FLD-024 — Reopen my own closed job before the office accepts it, or raise the next one

**Requirement 24, in the design's words:** *Reopen a closed job, or raise the next one — a disconnect becomes a reconnect once payment lands* — section D · Asked for by the technicians · standing *New*.

**1 · Details** — As **Dana**, I want **to reopen WO-4822 if I got it wrong, until the office accepts it, and to raise a reconnect as a new order**, so that **corrections and follow-ons are distinguishable**. After acceptance it is a correction and the office owns it (R22); a reconnect is a new work order, never a reopen (R21), and needs office approval (R23).

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-35` Completed — [phone](../wireframes/phone/FF-35-completed.png) · [tablet](../wireframes/tablet/FF-35-T-completed.png)<br>`FF-36` Reopen — [phone](../wireframes/phone/FF-36-reopen.png) · [tablet](../wireframes/tablet/FF-36-T-reopen.png)<br>`FF-37` Raise — [phone](../wireframes/phone/FF-37-raise.png) · [tablet](../wireframes/tablet/FF-37-T-raise-an-order.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00021` | R21 | A reconnect is a new work order, never a reopen. | CONFIRMED (PO) |
| `BR-FLD-00022` | R22 | A technician may reopen their own job before the office accepts it. | CONFIRMED (PO) |
| `BR-FLD-00023` | R23 | A field-raised reconnect needs office approval. | CONFIRMED (PO) |
| `BR-FLD-00024` | R24 | A field-raised order gets no number until it syncs. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-35: WO-4822 Passed 09:58, *Waiting for the office* → *Reopen*, reason *Missed a step* | The close is undone; the office is told |
| TC-2 · **negative** | WO-4801 *Passed · accepted* | *Reopen* is greyed — it is the office's correction now (R22) |
| TC-3 | *Raise reconnect* on WO-4801 | FF-37 opens a NEW order carried from WO-4801; it lands pending office approval (R21, R23) |
| TC-4 | E2E-17 / E2E-18 | The office reopens the same order or raises a linked one, and the two are distinguishable |
| TC-5 | A field-raised order before sync | No number — *Number arrives when this sends* (R24) |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — WO-4822 Passed 09:58 not accepted · WO-4801 Disconnect accepted · WO-4815 Waiting on someone (no access).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| reopen | FF-36 | R22 | outbox `reopen` (reason) | choice | user-input | only before acceptance |

**6 · Acceptance** — **Given** a closed job not yet accepted, **when** the technician reopens it with a reason, **then** the close is undone and the office is told; after acceptance the control is unavailable.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
