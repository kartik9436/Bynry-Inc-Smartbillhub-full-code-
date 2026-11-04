# A portal move-in / new-connection request, carried to an active customer

PO ruling 2026-10-01 (decision log, top row): *"complete the move in process or new
conenct request coming from portal - extend it until entire process is completed and
customer is activated; you will ahve to create regular or master customer; you will
ahve to create or link customer ID - those cases also should be tested"*, and *"in the
process if you find the bugs fix it"*.

Test utility for this lane (PO via coordinator, 2026-10-01): **six services switched
on — water, trash, sewer, fire, solar, battery.**

## BEFORE — what the code did at `558e75aba`

Measured by reading the code, then by running the backend walk on PostgreSQL 16
(`06-backend/tests/test_portal_request_to_active.py`). Each step is marked
**AUTO** (the product does it), **CLERK** (a clerk screen does it) or **MISSING /
BROKEN**.

| # | Step | Move-in (premises + unit exist) | New connection (unknown address) |
|---|------|------|------|
| 0 | Applicant sends the portal form (`CWP-009`) | AUTO — request `SR-` created, channel *Customer portal*, state Submitted | same |
| 0a | The services the applicant ticked reach the request | **BROKEN** — written as one prose sentence (*"Applied through the customer portal for: water, sewer"*); no `service_request_services` row, so the Services table, the move-in job's *services asked for* and the build's prefill are all empty | same |
| 1 | Clerk finds / links an existing customer, or records "no prior customer" | CLERK — Decision tab, `link_customer` | same |
| 2 | Clerk sets the customer class | CLERK — capture step 2 chips (`set_customer_category`) | same |
| 3 | Clerk approves as move-in / new connection | CLERK — Approve modal (`approve_and_raise`) → pending move-in job | CLERK — Approve modal → DRAFT build with no premises |
| 4 | The linked customer is used when the account opens | **MISSING** — the move-in wizard reads name, email, phone, date of birth from the request and never its linked customer, so a clerk who linked `C-…` on the Decision tab gets a SECOND customer number unless a government identifier happens to match | AUTO — the build wizard's owner step prefills `matched_customer_id` |
| 5 | The class picked on the request reaches the account | **MISSING** — the move-in wizard's class starts blank; the request's class is never read | **MISSING** — the build's owner block does not read it |
| 6 | Premises / unit | exists | AUTO at the build's last button — premises created from the wizard's address block (`_commit_raised_draft`) |
| 7 | Service points / connections, with SIZES for trash, fire, solar, battery | exist on the unit | **BROKEN — `DEF-MET-6119`, open since 2026-09-21**: only METERED services travel on the commit payload, so trash, fire, solar and battery are recorded nowhere, and no cart / fire line / panel / battery is created, so no size is held |
| 8 | Meter | exists | AUTO — created *not installed*; installed when the field work order is accepted |
| 9 | Plan | assigned to the unit | CLERK — build step plans |
| 10 | Start read | CLERK — move-in wizard step 3 | after install |
| 11 | Account → ACTIVE, regular | CLERK — move-in wizard (`POST /units/{id}/move-in`), closes the move-in job | CLERK — first-occupant move-in on the new unit |
| 12 | Account → ACTIVE, **master** (owner / manager of a multi-unit premises) | **MISSING** — the master-account door takes no request, so it cannot fulfil an approved move-in and its job stays pending for ever | CLERK — the build's *create owner account* (`create_owner_account`) |
| 13 | Portal user can sign in and see the account | AUTO for a linked customer who already has a login (the account set is read from `customer_accounts` at sign-in); a new customer enrols on account number + postcode + name | same — but only if the new premises was given a postcode |

## AFTER — what the code does at `ec3de65bd` (`CR-159-BRC10`)

| # | Step | Move-in | New connection | Built by |
|---|------|------|------|------|
| 0a | Ticked services reach the request | **AUTO** — one row per service | same | `DEF-CUS-9034` |
| 4 | The linked customer is used | **AUTO** — the server adds the request's linked customer wherever the wizard names none; no second customer number | AUTO (owner step) and now also server-side | `DEF-CUS-9035` |
| 5 | The request's class reaches the account | **AUTO** — the move-in wizard prefills it; the server fills it when a payload sends none | **AUTO** for the owner's master account | `DEF-CUS-9035` |
| 7 | Services and SIZES on a build | n/a | **AUTO at the build's last button** — every service recorded with a service point; a cart, panel or battery of the size the grid shows, created numbered and not installed | `DEF-MET-6119` |
| 12 | Master account | **CLERK** — request page → *Owner's master account* → the property's Common areas form (`?request=`); the job closes, the applicant is carried when no customer is linked | CLERK — owner step, now carrying the request's link and class | `DEF-CUS-9036` |
| 13 | Portal user sees the account | AUTO (proved: new customers enrol; a linked customer's existing login sees the new account) | same | — |

**Still open, stated:**
* **Fire's device** is not offered by New Connect, so the wizard cannot size a fire
  line — `OQ-1361`'s open half (`BR-AST-042`). The server records one when named.
* **`DEF-MET-9037`** — a solar or battery build also fits an UNSIZED net meter on the
  capacity point; once installed it will refuse that account's bill. Filed for a ruling.
* **A new connection's start read** comes with the install work order: the build's meter
  is created *not installed* (PO 2026-09-21), so the occupant's account is ACTIVE before
  any reading exists.

## The tests

`06-backend/tests/test_portal_request_to_active.py` — nine cases on PostgreSQL 16 on a
utility selling water, trash, sewer, fire, solar and battery. Every case starts at the
portal's own two doors and ends with the account ACTIVE and the portal user seeing it;
every row is read back from the database and through the screens' reads.

| Case | Shape | Customer | Account | Services |
|---|---|---|---|---|
| 1 | move-in | new | regular | water (+ a contact correction: one field, one history row) |
| 2 | move-in | linked | regular | trash |
| 3 | building on file | new company | master | fire |
| 4 | new connection, unknown address | new | regular | all six |
| 5 | new connection | linked | master (owner) | solar |
| 6 | new connection | new company | master (owner) | battery |
| 7 | move-in | new | regular | sewer |
| 8 | building on file, master FORM | new person (carried) | master | water + sewer |
| 9 | the legacy eighth class `government` is refused on a new request | | | |

Each fix was proved RED first by switching it off: services (7 of 8 cases red), the
request decisions (5 red), the build's services and sizes (3 red), the master door's
job close (1 red), the applicant carry (1 red). Front end:
`07-frontend/src/features/customers/newConnectUnitServices.test.ts` (2 of 3 red without
the wiring).
