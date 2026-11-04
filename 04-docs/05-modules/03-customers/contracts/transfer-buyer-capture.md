# The transfer's buyer — what it carries, what is required, which door

**`BR-CUS-1081` · PO ruling 2026-09-20 · backend landed · ⚠ FRONT END LANDED
2026-09-20 in `2.318.0` — this line read *"front end owed"* until then.**

> **WHAT THE SCREEN DOES NOW, so the next lane reads the built state and not the
> owed one.** `TransferWizard.tsx` step 2 renders `applicantCapture.tsx` — the
> move-in capture's own applicant block, lifted into a component so the PO's
> *"we have it … use it"* was a thing a lane could actually do; it was 120 lines
> INLINE in a 4,186-line page and importable by nothing. The step captures §2's
> optional fields (date of birth, driving licence, SSN, phone, email,
> co-applicant), §3's mailing address behind one checkbox with its absence
> STATED, and calls §4's `POST /transfers/buyer-preview` as the buyer is typed,
> rendering the drawn *"Matched an existing customer."* line.
>
> **TWO THINGS ARE DELIBERATELY NOT BUILT AND ARE NOT OVERSIGHTS.**
> (a) `preferred_language` is in `CAPTURE_FIELDS` and is NOT drawn: the move-in
> capture the PO named as the benchmark does not ask for it, p126/p127 do not
> draw it, and the account's column is nullable — decision log 2026-09-20.
> (b) `ServiceRequestCapturePage` still renders its OWN copy of the fields: a
> sibling collapsed them into one `FieldGrid` on 2026-09-19 to close a B14 rule
> 39 spacing defect, and this two-grid component would re-open it. The two are
> held together by a guard in `applicantCapture.dom.test.tsx` that fails if the
> shared block ever labels a field the capture page does not.
>
> **§5's KYC UPLOAD IS STILL OWED BY THE SCREEN.** The account's own filing
> cabinet (`POST /accounts/{id}/documents`, `doc_type: "kyc"`) needs no new
> endpoint and step 2 does not yet point at it.

> PO, verbatim, having walked the wizard in the live product:
> *"step 2 dont allow to take kYC documents - DOB, all detaisl we need to create
> account - Similar to Move in request we will need all details for account"*
>
> and, when told a backend lane would be needed:
> *"we have it - we have created it for service request move in - use it"*

**This file is the contract the `TransferWizard.tsx` lane is unblocked by.** It
is written for somebody building the screen, so every field says where it goes
and what happens if it is absent.

---

## 1 · The short version

A transfer's buyer now carries **eleven captured fields plus a mailing address**,
where it used to carry a name, a kind and one identifier. The set is **reused**,
not copied: `transfers.BUYER_CAPTURE_FIELDS` is derived from
`service_request_service.CAPTURE_FIELDS` — the move-in request's own capture
vocabulary, which is what the PO pointed at — and
`transfers._capture_vocabulary()` **raises** if the two ever drift.

**Three fields are required. Everything the ruling added is optional.** That is
a judgment with a reason, not a default: the PO named the move-in request as the
benchmark, and on that form a date of birth, an email, a phone, a language, a
co-applicant and a mailing address are every one of them optional. Making a SALE
stricter than the application the PO pointed at would refuse a buyer at the
counter for a field the benchmark does not ask for.

---

## 2 · The fields

### Required — refused at step 2 and again at commit

| Field | Also accepted as | Why it is required |
|---|---|---|
| `applicant_name` | `display_name`, `name` | `BR-CUS-1023` — a customer number needs a name |
| `applicant_kind` | `kind` — `person` \| `company` | `BR-CUS-1022` — it decides which identifiers mean anything |
| **one** identifier for that kind | see below | `BR-CUS-1030` — *no account may exist with nobody identifiable behind it* |

A **person** is identified by `ssn`, `drivers_licence` or `applicant_phone`; a
**company** by `tax_id`. Identifiers may arrive **flat** (the capture spelling)
or nested under `identity{}` (what the shipped wizard sends). Both work; on a
clash the nested block wins.

### Optional — captured, and each lands somewhere

| Field | Lands on | Absent means |
|---|---|---|
| `date_of_birth` | `customers.date_of_birth` **and** `contacts.dob` | **no match can ever be `strong`** — see §4 |
| `applicant_email` | `contacts.email` | ~~the account keeps the **seller's** email~~ **the seller's is REMOVED; the account has none** (T3, 2026-09-23) |
| `applicant_phone` | `contacts.phone` (and is an identifier) | ~~the account keeps the seller's phone~~ **removed, as above** |
| `preferred_language` | `accounts.preferred_language` | unchanged |
| `ssn` / `drivers_licence` | `customers`, app-layer encrypted | a weaker match |
| `co_applicant_name` / `_email` / `_phone` | ~~nowhere — `OQ-CUS-12514`~~ **`contacts`, the account's NON-primary row** (T4, `OQ-CUS-12514` closed 2026-09-23) | no second person; an earlier one is removed |
| `mailing_address{}` | `customers.addresses` `kind='mailing'` (`line2` accepted) | ~~the bill goes to the seller's address~~ **the seller's mailing row is REMOVED and the bill goes to the service address** (T3) |
| `customer_id` | ⊕ **2026-09-23 (T1, `DEF-CUS-6386`)** — the buyer the clerk LINKED with the step-2 finder | a new customer is created from the fields above; **with it, no identifier is required** — the customer already has one; an id that is malformed, unknown or another tenant's earns no exemption and is never refused by itself (`DEF-CUS-5974`: a half-typed id is *not recognised, never a 500*) |

⚠ **A company is refused `date_of_birth` and `drivers_licence` by name**
(`BR-CUS-1022`), through the service request's own guard, so the sale and the
application refuse the same field in the same words.

---

## 3 · The mailing address

```jsonc
"mailing_address": {
  "line1": "PO Box 4120",   // REQUIRED when the block is present
  "city": "Austin",
  "state": "TX",
  "postal_code": "78704"
}
```

**PO-ruled the same day: *"please add it at buyer"*** (decision log 2026-09-20,
*The transfer's buyer carries a mailing address*).

**This is CLAUDE.md hard rule 8's first named exception and the only lawful
second address in the product** — *"where the BILL goes, which for a landlord is
another building"*. No address column is added anywhere; the write goes through
`services.update_account_mailing_address`, the door that already exists.

* `kind` is **not accepted** — the door writes `mailing` and only `mailing`, so
  the retired `kind='service'` cannot arrive even as a typo.
* `line2` and `country` are **not accepted**, and that is a gap in the write
  door rather than a choice here — `DEF-CUS-5942`. Both are real columns since
  `customers 0039`; `services.ADDRESS_FIELDS` was never widened to match. The
  buyer's set is derived from that door's vocabulary, so it gains them the day
  the door does.
* **Omitting the block is a real answer and the screen must say so.** The
  account keeps the mailing row it had, which is the **seller's**, and the
  commit reports `mailing_address_still_the_sellers` in `unavailable`. Nothing
  is guessed: `BR-NOT-029`(a) forbids deriving an address from a name, a
  premises or the tenant's own country.

---

## 4 · The match, told BEFORE the commit

**New door — `POST /transfers/buyer-preview`.** It takes a `customer` block,
writes **absolutely nothing** (no transfer row, no customer, no audit row) and
answers whether this buyer is already on file.

```jsonc
// POST /transfers/buyer-preview   { "customer": { …the block above… } }
{
  "buyer_name": "Okafor, Chidi",
  "buyer_kind": "person",
  "buyer_identifiers_presented": ["phone", "ssn"],
  "buyer_capture_presented": ["applicant_email", "date_of_birth"],
  "buyer_mailing_presented": true,
  "buyer_match": {
    "verdict": "named" | "matched" | "candidates" | "none",
    "matched": "<customer id>" | null,
    "tier": "strong" | "weak" | null,
    "basis": "name and Social Security number",
    "candidates": [ … ],
    "missing_for_strong": ["date_of_birth"],
    "will_create": false
  }
}
```

This is the drawn feedback line on p126 — *"Matched an existing customer.
C-00902 · Vasquez, M., on the phone number."* — and the step's own help,
*"Matched first, created only on no match"*, stated back about the buyer being
typed.

**The four verdicts, and `named` is not `matched`:**

| `verdict` | what it means | what the commit will do |
|---|---|---|
| `named` | the clerk POINTED at a customer — `customer_id` or `external_ref` — and it exists | use exactly that one; **no evidence is weighed, so `tier` is `null`** |
| `matched` | the evidence agreed with exactly one customer | reuse them, `tier: "strong"` |
| `candidates` | somebody looks related and the criteria are not met | **create a new customer beside them** |
| `none` | nobody on file | create a first-timer |

⚠ **`named` was added on 2026-09-20 after the first build — `DEF-CUS-5974`.**
The preview modelled the matcher alone, and `services.link_customer` resolves a
NAMED customer and a legacy `external_ref` before and after it. So a block
carrying either key was told `will_create: true` about a buyer the commit was
going to reuse — the exact wrong answer this door exists to prevent, told with
confidence. It was unreachable from the wizard (which sends neither key) and
every test written against that screen was green.

⚠ **A half-typed `customer_id` answers `will_create: true`, never an error.**
The screen may call this on every keystroke.

* **It is a POST that writes nothing, deliberately.** A `GET` would put a
  government identifier in a URL, and a URL is logged by every proxy, appears in
  browser history and lands in the next request's referer header.
  `BR-CUS-092`(c) is about exactly that class of leak.
* **It refuses exactly what the commit refuses** — the same `_validated_buyer`.
  A preview that accepted a block the commit rejects would be worse than no
  preview, because the clerk would trust it.
* **`missing_for_strong` is the half that makes it actionable.** `BR-CUS-089`
  wants **name + date of birth + one government identifier**, so a buyer with a
  candidate and no date of birth is *one question away* from reusing a customer
  instead of minting a second one. `DEF-2587` measured what the second one
  costs: a landlord written as `C-00001`, `C-00002` and `C-00003` over one
  Social Security number.
* **It is advisory and refuses nothing** — `BR-CUS-019`, *the duplicate check is
  ADVISORY; staff decides*.

`POST /transfers/commit` carries the same block under `buyer_match` on its step-2
response, for a service-layer caller that never sees the preview door.

---

## 5 · KYC documents — the existing door, and nothing new

**A transfer buyer's documents do NOT ride `service_request_documents`, and they
must not.** That table's `request_id` is a non-null `PROTECT` foreign key to
`service_requests`; a transfer has no request row, and minting an empty one to
hold a file would be the second weaker home for a person's evidence that
`BR-CUS-1020` exists to stop.

**They ride the account's own filing cabinet, which already exists and already
has the category the rule names:**

```
POST /accounts/{id}/documents     doc_type: "kyc"     (multipart)
GET  /accounts/{id}/documents
```

`BR-CUS-036`'s type lookup is *System/Contract/KYC/Payment/Correspondence*, and
`kyc` is both **uploadable** and **withdrawable**. The account being sold exists
before step 1 and is on screen at step 1, so the wizard points its upload at that
account and needs no new endpoint, no new table and no new migration.

⚠ **Two things the account's cabinet does NOT have, stated rather than
discovered:**
1. **No `what_it_proves` column.** `service_request_documents` has one and
   `account_documents` does not, so *what a document proves* — the field
   `DEF-CUS-5907` restored on the request side today — has nowhere to go on a
   sale. Filed as **`DEF-CUS-5943`**.
2. **One artefact per content type per account.** `uq_stored_documents_filed`
   allows one `(tenant, source_type, source_id, content_type)`, so a **second
   PDF** on one account is refused by the database. Two PDF scans of a buyer's
   evidence cannot both be filed. Filed as **`DEF-CUS-5944`**.

Neither is this lane's to fix and neither blocks the screen: a single JPEG or a
single PDF per account files correctly today.

---

## 6 · What the commit answers

⊕ **AMENDED 2026-09-23 — the four PO rulings T1–T4 (`DEF-CUS-6387`, `6391`,
`6393`, `6394`).** Three of the stated absences below became writes, and the
owner's became a move for a master account. The response now reads:

```jsonc
{
  "buyer_carried": {
    "written": ["contact", "mailing_address" | "mailing_address_removed",
                "autopay_removed", "co_applicant", "preferred_language"],
    "not_written": []
  },
  "customer_match": { … },          // unchanged — what link_customer did
  "premises_owner": { "state": "unchanged" | "moved" | "not_moved", … },
  "unavailable": [
    { "code": "premises_owner_not_moved", … },   // a MASTER sale only, with its reason
    { "code": "account_had_no_contact_row", … }
  ]
}
```

**Retired, and a client reading them reads nothing:**
`premises_owner_record_not_updated` (a regular sale moves no owner and states
nothing; a master sale moves it), `mailing_address_still_the_sellers` and
`contact_details_still_the_sellers` (T3 removes them), and
`co_applicant_captured_and_not_stored` (T4 stores it).

`account_had_no_contact_row` deserves a note: `update_account_contact` is a
CORRECTION path and refuses an account carrying no contact row. That refusal is
right for a PATCH and would be wrong here — **a buyer must not lose a property
because a row nobody ever created is missing** — so the sale completes and the
absence is reported.

---

## 7 · What did NOT change

* **The three required facts are still exactly three.** Nothing the ruling added
  is compulsory.
* **`transfers` gains no column for the BUYER.** Not for a date of birth, not
  for an email, not for an address. ⊕ **It gained one for the SELLER on
  2026-09-23 — `seller_name` (`customers/0068`, `DEF-CUS-6387`)** — because an
  account with no linked customer now sells, and the name on the account is
  then the only record of who sold it. `set_new_customer` still *"validates and stores nothing"*
  — that sentence now covers eleven fields instead of five, and the reasoning is
  unchanged: a workflow table must not become a second home for a person.
* **The shipped wizard payload still sells a property.** `display_name`, `kind`,
  `identity{}` and `email` all still work; the capture spellings are canonical
  and the old ones are aliases.
* **Hard rule 4 is untouched.** No invoice, invoice line, payment or journal
  entry is written, updated or deleted by any of this.
