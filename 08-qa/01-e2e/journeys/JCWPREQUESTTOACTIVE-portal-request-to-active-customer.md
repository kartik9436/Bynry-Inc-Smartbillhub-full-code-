# JCWPREQUESTTOACTIVE — a portal application becomes an active customer

---
id: JCWPREQUESTTOACTIVE
tier: 1
rules: [BR-CUS-068, BR-CUS-080, BR-CUS-094, BR-CUS-1024, BR-CUS-1077, BR-CUS-1101,
        BR-CUS-1111, BR-CUS-1112, BR-CUS-1113, BR-MET-112, BR-MET-1188, BR-CWP-029,
        BR-CWP-030, BR-RAT-090, BR-TEN-171]
stories: [US-CWP-014, US-CUS-004, US-CUS-026]
# ⚠ **A COMMITMENT WRITTEN DOWN, NOT YET A BROWSER SPEC.** PO ruling 2026-10-01
# (`CR-159-BRC10`): *"complete the move in process or new conenct request coming
# from portal - extend it until entire process is completed and customer is
# activated; you will ahve to create regular or master customer; you will ahve to
# create or link customer ID - those cases also should be tested"*. The backend
# walk runs today (`06-backend/tests/test_portal_request_to_active.py`, nine
# cases, PostgreSQL); the browser walk is a sibling lane's, after this one pushed.
---

## The utility

Six services switched on, as the PO named them on 2026-10-01: **water, trash, sewer,
fire, solar, battery.** Every service is asked for on its own at least once, and one
application asks for all six.

## The handoff contract

| Step | Who | Leaves in the database |
|---|---|---|
| 1 · Apply (`CWP-009`, `PUT` the draft, `POST …/submit`) | applicant, no login | `service_requests` row, channel *Customer portal*, state Submitted; **one `service_request_services` row per ticked service** (`BR-CUS-1113`) |
| 2 · Pick the property off the register (where the typed address did not resolve), link or record *no prior customer*, set the class | clerk, request page | `resolved_premises_id` / `resolved_unit_id`, `matched_customer`, `account_type` |
| 3 · Approve as **move-in** or **new connection** | clerk, Approve modal | a pending `move_in_jobs` row, or a DRAFT `connections` row with no premises |
| 4a · Move-in wizard on the unit (`?request=`) | clerk | account ACTIVE, regular, on the LINKED customer or a new one, with the request's class (`BR-CUS-1111`); move record names the request; the job is done |
| 4b · Owner's master account (request page → property's Common areas, `?request=`) | clerk | master account ACTIVE on the premises; job done with `master_account_opened`; `service_request.fulfilled_by_master_account` audited (`BR-CUS-1112`) |
| 4c · New Connect on the draft build | clerk | premises (with postcode), units, water meter, a `connection_services` row and service point for every service, sized cart / panel / battery (not installed), plan; with an owner, the owner's master account on the request's linked customer and class (`BR-MET-1188`) |
| 5 · First-occupant move-in on the new unit | clerk | regular account ACTIVE taking every service of the unit |
| 6 · Sign in | customer | a new customer enrols on account number + postcode + name (`BR-CWP-030`); a linked customer who already has a login sees the new account at the next sign-in |

## The cases (`tests/test_portal_request_to_active.py`)

| # | Shape | Customer | Account | Services | Class |
|---|---|---|---|---|---|
| 1 | move-in | new | regular | water | residential — plus a clerk correction of the contact email (one field moves, one history row) |
| 2 | move-in | **linked** (company on file, person applying) | regular | trash | commercial — the existing login now sees two accounts |
| 3 | building on file | new (company) | **master** | fire | institutional, carried from the request |
| 4 | **new connection, unknown address** | new | regular | **all six** | industrial |
| 5 | new connection | **linked** | **master** (owner) | solar | builder_developer, carried |
| 6 | new connection | new (company) | **master** (owner) | battery | agricultural, carried |
| 7 | move-in | new | regular | sewer | municipal, carried (payload sent none) |
| 8 | building on file, via the master FORM (payer name only) | new (person, carried from the applicant) | **master** | water + sewer | residential |
| 9 | — | — | — | — | `government`, the eighth seeded class, is refused on a new request (`BR-CUS-094`) |

⛔ **A master account needs a building of two or more homes (`BR-CUS-1114`, PO 2026-10-02).**
Cases 5 and 6 build TWO units for that reason. On a single-home address every master door
refuses (*"Single unit. Open a regular account."*) and the applicant gets a REGULAR account
on the one unit through Move-in, holding the services, ACTIVE; a single-home new build raises
no owner's master account (`BR-CUS-1115`) —
`tests/test_br_cus_1114_master_only_multi_unit.py`.

## Known limits, stated

* ~~Fire's device is not offered by New Connect~~ — **lifted 2026-10-02** (`OQ-1361` CLOSED
  by the PO): step 3 offers the fire line, one row per piece; 1 × 6" + 2 × 2" bills `$84.00`.
* ~~`DEF-MET-9037`~~ — **lifted 2026-10-02** (PO: *"Capacity is the panels or battery only"*):
  a solar or battery build fits no meter, and a meter on the point never counts.
* **The start read of a new connection** comes with the install work order, not the
  move-in: the build's meter is created *not installed* (PO 2026-09-21).
