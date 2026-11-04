# customer-told-about-a-visit — a customer hears that a visit is booked, moved, on its way and done, and the office hears when a job is declined, on hold or at risk

---
id: customer-told-about-a-visit
tier: 2
change: CR-168-BRC10 P6.8 (round 6, lane SRV-5, `2.517.0`)
rules: [BR-NOT-017, BR-NOT-021, BR-NOT-005, BR-WRK-025, BR-MET-110, OQ-WRK-1495]
modules: [work, notifications, customers, metering]
spec: 06-backend/tests/test_cr168_srv5_messages.py (17 cases, SQLite and PostgreSQL 16)
walk: 10-scripts/cr168_srv5_walk.mjs (browser, 1440)
---

**Intent.** Ruling 3 (23 Sep): *"Notification reaches the consumer and the back office,
and work orders print."* This journey is the consumer and back-office half: one job
with a customer, from the moment it gets a date to the moment the office accepts it.

**Upstream leaves (preconditions).** A utility with its notification templates seeded
(`seed_notice_templates` — provisioning, or `manage.py seed_demo --tenant <subdomain>`
for a utility provisioned before `2.517.0`); a job raised on a unit whose account has a
contact; the account's own election — `paperless` (email) and/or `sms_reminders`
(SMS); a technician to send it to.

| # | Who | Does | The customer / office is told | Queue row |
|---|---|---|---|---|
| 1 | Dispatcher | Assigns the job with a date and window | **Booked** — email and/or SMS, as the customer elected | `appointment` · `appointment_window` · `service_appointment` / `sms_visit_booked` |
| 2 | Dispatcher | Moves the window | **Moved** — once per new window; the same window again tells nobody | `visit_moved` · `service_visit_moved` / `sms_visit_moved` |
| 3 | Technician (phone) | Declines, with a reason | Office: **declined** — whoever sent it to the field and every System Admin | `field_work` · `work_job_declined` |
| 4 | Dispatcher | Puts it on hold | Office: **on hold** — once per hold | `work_job_blocked` |
| 5 | Hourly sweep | Finds the promise inside the utility's at-risk window | Office: **at risk** — once per promise | `work_job_at_risk` |
| 6 | Technician (phone) | *On my way* | **On the way** — SMS | `technician_on_the_way` · `sms_technician_on_the_way` |
| 7 | Technician (phone) | Closes the job *Passed* | Nothing to the customer yet — the field close is not final (`WM-47`) | — |
| 8 | Office | Accepts | **Done** — email; never for a failed job | `completion_receipt` · `service_work_completed` |

**Rules the journey holds.**
* **No message without a rule (P6.6).** Each kind is its own row on Settings →
  Notifications; switched off, nothing is written. A utility seeded before `2.517.0`
  holds booked, on the way and done OFF (they were refused then) until a supervisor
  switches them on.
* **The customer's own channels.** A customer who elected neither email nor SMS gets
  nothing, and the act answers `visit_message_no_channel_elected`.
* **The do-not-send list holds, never drops** — the row is written `held`.
* **SMS is written unaddressed today** (`recipient_not_resolvable`): the platform holds no
  MOBILE number, and customers' read will not guess one from a landline.
* **No customer, no message** — a network job tells nobody.
* **The address is the premises'** (hard rule 8); no id travels in any message.

**Leaves (for downstream).** Outbound rows of kind `appointment` keyed by (job, kind,
occasion) — a replay writes nothing; in-app rows of kind `field_work` in each office
recipient's bell (`notifications.workOffice.*`, eleven catalogues).
