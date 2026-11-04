# CR-159-BRC10 — A portal move-in / new-connection request is carried to an ACTIVE customer

**Raised:** 2026-10-01, by the Product Owner, in the same exchange as `CR-158-BRC10`. The
ruling is the decision-log row dated 2026-10-01 headed *"CUSTOMERS MAY NOW UPLOAD DOCUMENTS
FROM THE PORTAL … AND A PORTAL MOVE-IN / NEW-CONNECTION REQUEST IS TO BE CARRIED ALL THE WAY
TO AN ACTIVE CUSTOMER"*, items (3)–(5).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed for this branch by `CR-156-BRC10`
in `12-governance/14-id-reservations.md`). Number from `10-scripts/allocate.py cr`, verified
free on every branch at push time (`--verify 159`).
**Classification:** a **CHANGE** (`13-change-process.md` §1) for the part that is new
— a request ending in a MASTER account at an address on file had no door — and four
**DEFECTS** for the parts the product already promised and did not do (§3).

## 0 · What arrived, in the requester's words

> *"also cna you complete the move in process or new conenct request coming from portal -
> extend it until entire process is completed and customer is activated; you will ahve to
> create regular or master customer; you will ahve to create or link customer ID - those
> cases also should be tested"*

> *"in the process if you find the bugs fix it"*

Added the same day, through the coordinator: *"When you take utilty take it for 6 utility
services water, trash, sewer, fire, solar and battery - self service portal"* and *"also
ensure you check the all data is correctly saved updated, viewed"*.

## 1 · What signed statement is reversed

None. No ❄️ B4/B5 figure moves. `BR-CUS-1024` (no identifier, no account), `BR-CUS-068`
(master account), `BR-CUS-1077` (the move-in job) and `BR-MET-112` (nothing written until the
build's last button) all stand and are what the new paths go through.

## 2 · Status

DONE `2.439.0` — see §3. Commit in §4. The step list before and after is
`08-qa/screens/portal-request-to-active-2026-10-01/STEPS.md`; the journey is
`08-qa/01-e2e/journeys/JCWPREQUESTTOACTIVE-portal-request-to-active-customer.md`.

## 3 · What was built

| Gap found | Record | Now |
|---|---|---|
| The applicant's ticked services reached the request only as a sentence | `DEF-CUS-9034` · `BR-CUS-1113` | one `service_request_services` row per service the utility sells |
| The move-in ignored the customer the clerk linked on the request, and its class — a second customer number | `DEF-CUS-9035` · `BR-CUS-1111` | carried wherever the payload is silent; the wizard prefills the class |
| No way to end an approved request in the OWNER's master account at an address on file | `DEF-CUS-9036` · `BR-CUS-1112` | the master door takes the request, closes its job, audits it; *Owner's master account* link on the request page |
| A build recorded no unmetered service and no size (trash, fire, sewer, panels, batteries) | `DEF-MET-6119` · `BR-MET-1188` | `unit_services` on the commit: service rows, service points, sized equipment (not installed) |

**Filed, then FIXED `2.440.0` by PO ruling 2026-10-02:** `DEF-MET-9037` — an unsized
net meter on a solar or battery point would refuse that account's bill once installed. PO:
*"The net meter doesn't count toward capacity. Capacity is the panels or battery only."* A
solar or battery build now fits no meter, and a meter already on such a point is never counted
or summed (3 × 4 kW bills 12 kW).

**Ruled by the PO 2026-10-02 and BUILT `2.440.0`:** New Connect offers the fire line —
*"A fire service gets a "fire line" item with a size (2" to 10"), like a trash cart. The clerk
picks the size on New Connection."* (`OQ-1361` CLOSED). One 6" and two 2" lines bill `$84.00`.
(This paragraph read *"Needs the PO … whether a fire service point takes `fire_line` is
`OQ-1361`'s open half"* until then.)

## 4 · Version, commit, rollback

Code: `ec3de65bd` (pushed 2026-10-01). **Version `2.439.0`** (`CHANGELOG.md`,
`--bump change`). **Rollback:** revert the code commit; no migration, no data written at
rest changes shape (the new rows are ordinary `service_request_services`,
`connection_services` and `assets` rows).
