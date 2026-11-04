# EP-FLD-08 — The technician — profile, availability, shifts, timesheet, admin time

**Module:** field-app (`18-field-app`, module code FLD) · **Wave:** 9 · **Design tasks:** T-24 · **Screens:** FF-44, FF-45, FF-46, FF-47, FF-48 · **Status:** draft (2026-10-21, `CR-187-BRC10`)

## Scope

**In:** the design's flow group *FF-44 to FF-48* and the requirements whose screens sit in it — US-FLD-006 (requirement 6), US-FLD-017 (requirement 17).

**Out:** everything the design's *Scope · Out* list excludes (`01-overview.md` §5) — taking payment on site, linear assets, inspection rounds, offline maps, a dispatcher app, live crew tracking, van stock-takes, customer-facing features, a watch app.

**Source:** the *SMART360 Next Field App* design canvas, version of 2026-10-21. The screens are the images in `../wireframes/` and they are the specification (B14 rule 42; PO 2026-10-21, *"please ensure all native app screens are build using images not using text or contents"*). Figures on a board are illustrations (B14 rule 37) and are used below as test data only.

## Capability matrix (list screens only — B9 conformance)

No list screen in this group.

## Stories

---
id: US-FLD-006
epic: EP-FLD-08
module: field-app
screens: [FF-44, FF-45, FF-46]
wave: 9
status: ready
blocked_by: []
depends_on: [US-FLD-032]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00038]
golden_tests: []
finance_calc: none
---
### US-FLD-006 — Identity and availability — profile with photo, language, availability, shifts, time off, holidays

**Requirement 6, in the design's words:** *Identity and availability — sign in, sign out, profile with photo, runtime language switching, Available / On break / Off duty, shift calendar, time off, utility holidays* — section A · The original brief · standing *Partly*.

**1 · Details** — As **Dana**, I want **my profile, my availability and my week of shifts on the phone**, so that **dispatch knows when I can take work**. Available / On break / Off duty; time off and utility holidays.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-44` Profile — [phone](../wireframes/phone/FF-44-profile.png) · [tablet](../wireframes/tablet/FF-44-T-profile.png)<br>`FF-45` Availability — [phone](../wireframes/phone/FF-45-availability.png) · [tablet](../wireframes/tablet/FF-45-T-availability.png)<br>`FF-46` Shifts — [phone](../wireframes/phone/FF-46-shifts.png) · [tablet](../wireframes/tablet/FF-46-T-shifts.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00038` | R38 | A technician taps, never types. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-44 | D. Ortiz · Water II · Available · On duty since 07:40 · Today 4 done, 7 left, 5h 2m worked · Silver Creek Water · Employee · (512) 555-0142 · 3 certifications current |
| TC-2 | FF-45 *On break* | *Emergencies still reach you* |
| TC-3 | FF-45 *Off duty* with 38 photos uploading | *Shift ends. Unsent work still sends.* |
| TC-4 | FF-46 this week | Thu 23 time off approved 02 Oct · Fri 24 utility holiday Founders Day, depot closed; *Request time off* |
| TC-5 · **negative** | Off duty | Unsent work is not held back |
| TC-6 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Shifts: Mon–Tue 08:00–16:30 Route 3 · Wed 06:00–14:30 Route 1 · Thu time off · Fri Founders Day.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| availability | FF-45 | requirement 6 | outbox `availability` → server | enum | user-input | three values |

**6 · Acceptance** — **Given** a technician, **when** they change availability or view their week, **then** dispatch sees the availability and the week shows shifts, time off and holidays.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---

---
id: US-FLD-017
epic: EP-FLD-08
module: field-app
screens: [FF-47, FF-48]
wave: 9
status: ready
blocked_by: []
depends_on: [US-FLD-029]
journeys: []           # the E2E-nn cases cited in §3 become journeys under 08-qa/01-e2e/journeys/ (sibling lane)
rules: [BR-FLD-00008, BR-FLD-00009]
golden_tests: []
finance_calc: none
---
### US-FLD-017 — Labour timesheet, not only a timer — where the hours go

**Requirement 17, in the design's words:** *Labour timesheet, not only a timer — where the hours go for payroll* — section C · From the reference apps, confirmed into scope · standing *New*.

**1 · Details** — As **Dana at the end of the day**, I want **jobs, travel and admin time on one timesheet I submit**, so that **payroll is right**. FF-48 times work that is not a job.

**Screens (build from the images — B14 rules 42, 44, 45):** `FF-47` Timesheet — [phone](../wireframes/phone/FF-47-timesheet.png) · [tablet](../wireframes/tablet/FF-47-T-timesheet.png)<br>`FF-48` Admin tasks — [phone](../wireframes/phone/FF-48-admin-tasks.png) · [tablet](../wireframes/tablet/FF-48-T-admin.png)

**2 · Business Rules**

| BR | R | Statement (first sentence, verbatim — the whole rule is in `02-business-rules.md`) | Status |
|---|---|---|---|
| `BR-FLD-00008` | R8 | Labour is per person, not per job. | CONFIRMED (PO) |
| `BR-FLD-00009` | R9 | Travel and labour are separate clocks — depart, arrive, start. | CONFIRMED (PO) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | FF-47 Today | 5h 02m recorded: jobs 3h 38m · travel 54m · admin 30m; WO-4824 running since 12:28 |
| TC-2 | FF-48 *Vehicle check* | 20m at 07:40, shown as admin |
| TC-3 | *Submit the day* | Sent to the office per person per order (R8) |
| TC-4 · **negative** | A running clock at submit | Shown as running; it is not silently stopped |
| TC-5 · **tenant isolation** | R. Patel works for Silver Creek Water and Lone Star Water and signs in to Lone Star Water on the same handset | Only `field-lone-star-water.sqlite` is opened; not one Silver Creek row is readable (R131), and the server takes the tenant from the credential, never from the payload (R127) |

**4 · Test Data** — Vehicle check 07:40–08:00 · WO-4822 08:46–09:58 · WO-4815 08:14–08:41 no access.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| time entry | FF-47/48 | requirement 17 | handset `crew_time` + admin entries | minutes | system-derived | correctable |

**6 · Acceptance** — **Given** a day of work, **when** the technician opens the timesheet, **then** jobs, travel and admin add up to the hours recorded and can be submitted.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
