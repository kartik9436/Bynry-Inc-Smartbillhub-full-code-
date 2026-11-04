# EP-NOT-05 — Notification rules: the event matrix and the per-event rule page

**Module:** notifications · **Wave:** W4 · **Screens:** S8 (Settings → Notifications — SET-12 matrix, SET-12D rule page) · **Status:** draft (BR-NOT-017 / BR-NOT-018 CONFIRMED by PO ruling 2026-08-17; OQ-261 and OQ-262 OPEN)

**Raised by CR-009 (2026-08-17), which is the source rather than a derivative** — the PO
wrote the requirement directly and said so: *"these screen are not there in R10; I have
just created it"*. There is no prototype to diff against and no extracted A1–A17 spec
behind these screens, which makes the CR text itself the authority and makes quoting it
verbatim more important than usual, not less.

## Scope

**In:** the SET-12 **event matrix** — one row per notification event with its audience,
channels, timing and an On toggle; **SET-12D**, the full-page rule editor for one event
(audience · channels & templates · timing · the escalation ladder for collections
events); the **"one home" consolidation** the PO ruled — *"we bring all internal external
ntification rule sat one place and they are part of notification settings"* — which
brings the collections chasing schedule and its two money thresholds onto SET-12D; and
**"Send test"**, which **ENQUEUES** a message to the signed-in user's own address.

**Out:** what a message SAYS (Configure → Templates, CR-007 — the CR's own stated
separation of concerns) · the dispatcher and the provider adapter (US-NOT-002 /
US-NOT-003, R3 by PO ruling) · the **medical / life-support skip and its CSR-task route**
(**PO ruling 2026-08-17: _"Skip it ; not required as this point of time"_** — absent by
ruling, recorded because the clause IS in the PO's written requirement) · the five
disconnect-notice clauses (the PO owns the wording; **_"Disconnect notice we will fix"_**)
· the Work → Rules triggers for the three field-work events (OQ-249, R5).

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S8 · SET-12 event matrix | event name | category (Billing/Payments/Collections/Field work/Staff & system), audience (Customer/Staff), state (On/Off) | catalogue order (the PO's own) | — (the order is the rule, not a preference) | Event · Audience · Channels · Timing · On · Actions | ✎ edit rule (opens SET-12D) · ➤ send test (queues) | — | — |

**Why the matrix does not sort and does not export.** Fifteen rows in a fixed, meaningful
order — a person finds a row by reading, not by sorting, and re-ordering would lose the
grouping the PO's requirement is written in. Export is deliberately absent for the reason
`SettingsNotificationsTab.tsx` already records for the queue list: the platform export
registry (IS-9) has no `notification_rules` resource, so a button here would post to a
registry that cannot serve it.

## Stories

---
id: US-NOT-017
epic: EP-NOT-05
module: notifications
screens: [S8]
wave: 4
status: draft
blocked_by: []
depends_on: [US-NOT-001, US-NOT-004, US-NOT-006]
journeys: []
rules: [BR-NOT-017, BR-NOT-018, BR-NOT-005, BR-NOT-013]
golden_tests: []
finance_calc: none
---
### US-NOT-017 — The notification event matrix (SET-12) and the event rule page (SET-12D)

**1 · Details** — As a System Admin I want ONE place that decides every message this
utility sends — customer and staff — so that turning off the hi-usage text does not mean
hunting through four settings screens, and so that the chasing schedule my collections
run obeys is visible next to the letters it sends.

SET-12 lists every event this platform can notify about, grouped in five categories, each
row showing who it goes to, on which channels, roughly when, and whether it is on. A row
opens SET-12D, a full page (not a modal) with four cards on the left — **Audience**,
**Channels & templates**, **Timing**, and, for collections events, the **Escalation
ladder** — and a right rail carrying the rule **in plain English**, the last 30 days of
delivery, and the audit note. Save is one transaction and returns to the matrix.

**THREE THINGS THIS STORY IS DELIBERATELY HONEST ABOUT, because a settings screen that
promises what the product cannot do is worse than a missing screen.**

**(a) Channels that do not exist.** The requirement names *Portal*, *Mail* and *In-app*.
This platform has three channels — print, email, SMS (BR-NOT-010) — and "Mail" on a
disconnect notice means physical post, which is a fulfilment vendor and not a flag. Each
is DRAWN, DISABLED, with its reason (BR-SHL-025). None is a toggle.

**(b) Events nothing can fire.** Three field-work events are *"fired by Work → Rules"*
and Work is R5 (OQ-249); three more — hi-usage alert, daily digest, security alerts —
have no trigger anywhere in this codebase at all (OQ-262). All six are drawn, and each
says so on its own row. Their audience, channel and template are still this screen's to
own, which is what the CR asks for.

**(c) Who a staff notification goes to is not ruled (OQ-261).** *"SLA breach (Owner
copied)"* has no addressee: "Owner" is not one of this platform's three roles, and the
PO's Settings-permission ruling answers who may CHANGE a rule, not who GETS an alert.
The Audience card offers no recipient and the service refuses every attempt to set one.

**WHAT "SEND TEST" DOES, and why it is not a reversal.** PO ruling 2026-08-17: *"lets
build the infra and capabilities; the moment we take the decison on ESP or SMTP from
existing email of Utilities, we just need to plug it ; rest of the infra will work"*.
BR-NOT-005's *"queue only, no synchronous send endpoint"* stands: the button writes a
real queue row addressed to the signed-in user, through the same and only write path
every bill uses, and the response reports the provider seam's own verdict — the row will
rest queued until an adapter is plugged in. No route named `send` or `test-send` exists
on this surface and a test asserts their absence.

**Entry:** Settings → Notifications. **Exit:** rules a future dispatcher and the
collections run obey; queue rows for tests.

**2 · Business Rules**

| BR-ID | Statement | Status |
|---|---|---|
| BR-NOT-017 | **ONE HOME for every notification rule, internal and external, and it is Settings → Notifications.** See 02-business-rules.md | **CONFIRMED — PO 2026-08-17** |
| BR-NOT-018 | **An event whose trigger does not exist is DRAWN and states so; it is never silently enabled and never silently omitted.** See 02-business-rules.md | **CONFIRMED — PO 2026-08-17** |
| BR-NOT-005 | Platform-wide outbound queue; the dispatcher is the only sender and no synchronous send endpoint may exist | CONFIRMED |
| BR-NOT-013 | Delivery is out of this release on every channel; `delivered`/`bounced` can never be written here | CONFIRMED |

**3 · Test Cases**

| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | A tenant that has never opened SET-12 reads the matrix | Fifteen rows in the catalogue's order, five categories, each with a complete stated rule — no empty table and no "unset" state |
| TC-2 | Read the matrix and count what the requirement claims | The response carries `requirement_claims_event_count: 16` beside `built_event_count: 15` — the discrepancy is DATA, not a note somebody remembers |
| TC-3 | Open SET-12D for `bill_ready` | Its channels are email and SMS; **Portal** is present in `unavailable_channels` with its reason and is NOT a togglable channel |
| TC-4 | Open SET-12D for `disconnect_notice` | The ladder card carries the tenant's own figures — reminder **3** days after due, tiers **10** then **5**, final **48** hours, floor **$25.00**, pause **25%** — read from the ONE store, and names `/settings/collections` as where they are written |
| TC-5 | A System Admin turns `past_due_reminder` off | Saved, one audit row `notification_rule.updated` carrying before→after of `enabled` only |
| TC-6 | A System Admin saves a rule with `trigger_mode: offset_days` and no `offset_days` | Refused by name — "'a number of days after the event' needs the number" — and nothing is written |
| TC-7 | A System Admin submits a `staff_recipient` for `sla_breach` | `NotImplementedError("OQ-261")`. No role is chosen, no column is written |
| TC-8 (neg) | An **Executive** PUTs a rule change | 403. The read still succeeds and every control renders disabled with its reason (BR-SHL-025) |
| TC-9 (neg) | A **Billing Clerk** GETs the matrix | 403 — A4 gives them no `settings_lookups` cell, and no cell is no access rather than read-only access |
| TC-10 | A System Admin clicks Send test on `bill_ready` / email | ONE queue row, `source_type: test`, addressed to **their own** email address, status `queued`; the response says `queued: true` and `will_be_delivered: false` with the seam's reason |
| TC-11 | Send test clicked twice | Two rows, `copy_no` 0 then 1 — the documented meaning of a deliberate extra copy — never one row and an `already_queued` problem |
| TC-12 (neg) | Resolve `/notification-rules/{event}/send` and `/test-send` | `Resolver404` on both. BR-NOT-005 stays visible rather than depending on nobody adding a route later |
| TC-13 (neg) | Enable a channel that has no template | Refused — *"a channel can't be enabled if its variant is deactivated"* — enforced in the service, not on the screen |
| TC-14 | The six events with no trigger | Ship `enabled: false` and carry `trigger_blocked_by` naming OQ-249 or OQ-262; the row is drawn either way |
| TC-15 (iso) | Lone Star Ridge's rules with Brazos Bend's `app.tenant_id` set | Invisible. RLS FORCE; a cross-tenant write would silently stop another utility's chasing letters |

**4 · UX Notes** — SET-12D is a full page, not a modal (the requirement is explicit). Row
actions are ICONS per B14 rule 1; one table type per B14 rule 3; the On toggle confirms
before it commits, because switching a collections rule off stops letters a utility's
receivables depend on.

**5 · Data** — `notification_rules` (one row per tenant × event) and
`notification_rule_channels` (one per rule × channel). **The escalation ladder's five
figures are NOT stored here** — see BR-NOT-017.

**6 · Dependencies** — US-NOT-001 (the queue the test send writes to), US-NOT-004 (the
dispatch config the global bar edits), US-NOT-006 (the template registry the channel
cards pick from).

**7 · Out of scope** — everything in the epic's Out list.

**8 · Open Questions** — **OQ-261** (who receives a staff notification) and **OQ-262**
(three events with no trigger and no owner). Both OPEN, both routed to the PO 2026-08-17,
both stubbed by name rather than guessed.

---
id: US-NOT-018
epic: EP-NOT-05
module: notifications
screens: [S8]
wave: 4
status: draft
blocked_by: []
depends_on: [US-NOT-001, US-NOT-002, US-NOT-003, US-NOT-004, US-NOT-006, US-NOT-017]
journeys: []
rules: [BR-NOT-019, BR-NOT-020, BR-NOT-005, BR-NOT-013, BR-NOT-009, BR-SHL-007, BR-SHL-026]
golden_tests: []
finance_calc: none
---

### US-NOT-018 — In-app: the one channel that needs nobody, and the ONE message a bulk action sends

**1 · Details** — As a Billing Clerk I want the run I just started to tell me it
finished — **once**, in the product I am already looking at — so that I learn about
three failed bills from a bell instead of from a customer, and so that a thousand-account
run does not leave me a thousand notifications to dismiss.

**WHY THIS STORY EXISTS AT ALL, and it is the PO's own reasoning rather than a
derivation.** Verbatim, 2026-08-17: *"We can confirm it whether it is working on not if
we get in APp Notifcaition, which does not require any integration and it is proof that
notification is working"*, then *"can you build the in-app?"*

Every other channel needs a third party before anything can be observed: email needs an
adapter and an SMTP-vs-ESP decision nobody has taken, SMS needs Twilio, print needs a
fulfilment vendor. **In-app needs nobody.** So a message arriving in an in-app inbox is
**proof the queue, the rule, template resolution, rendering and the dispatcher all work
end to end**, with the provider adapter the only remaining unknown. It is the product's
first demonstrable channel, and that is why it was built FIRST rather than fifth.

**WHAT THE STORY IS NOT.** It is not a second delivery path. The message travels the same
queue, the same dispatcher, the same ONE provider seam and the same rendered-artifact
contract every other channel will travel — the only difference is that the adapter behind
the seam is this application. A message written straight into an inbox by the caller that
raised the event would have proved that a row can be inserted into a table, which nobody
doubted.

**THE SECOND HALF IS A PRODUCT RULE AND IT IS THE MORE CONSEQUENTIAL ONE.** PO verbatim:
*"for single notification send 1 message and for bulk action also send 1 message only
saying nulk action is completed"* (BR-NOT-020). The staff events are precisely the bulk
ones, so without it a bill run over a thousand accounts is a thousand notifications — and
the first thing any clerk does is switch the event off, at which point **the failure they
needed to see is the one they never get.** And the summary must state a failure COUNT
where there were failures: hiding one is the same failure in the opposite direction.

**2 · Acceptance**
1. `in_app` is a channel of the platform, its route is **dispatchable**, and print, email
   and SMS still refuse for exactly the reasons they refused before (BR-NOT-013).
2. A delivered message lands in a **per-recipient** store, tenant-scoped with RLS FORCE,
   and no read anywhere accepts a user id from a request.
3. A bulk operation over 200 items queues **exactly one** message, and it states the
   failure count.
4. The **bell** shows the unread count, the popover lists the messages newest-first, and
   opening one marks it read.
5. **No `send` or `test-send` route exists** on this surface (BR-NOT-005, A11 r2 §4).

**3 · Test cases**

| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Read `models.CHANNELS` and route `in_app` for a tenant | Four channels; `in_app` answers `dispatchable: True` — the first channel in this product's history that does |
| TC-2 | Route print, email and SMS in the same tenant | All three still refuse: print `provider_not_connected`, email deferred to **W6**, SMS to **v1.1**. In-app must not have loosened anybody else's verdict (BR-NOT-013: *"no lane is to build or fake an adapter to turn a test green"*) |
| TC-3 | A staff event fires over **1,204** accounts with **3** failures, then the dispatcher runs | ONE queue row → `sent` (never `delivered`); the recipient's inbox holds one message reading **"Billing run finished. 1204 processed · 3 failed"**, with no named-absence mark in it |
| TC-4 | The same dispatch cycle runs again over the same row | The inbox still holds **one** message, and the cycle reports it **sent** rather than failed — `uq_in_app_msgs_message_user` refuses the copy and a retry must not burn attempts against a constraint that will always refuse |
| TC-5 | A bulk operation over **200** items | `OutboundMessage.objects.count()` grows by **exactly 1**. A COUNT, not a shape assertion — a shape assertion passes on 200 rows that all look right |
| TC-6 | The same bulk run is retried with the same run id | No second summary. The queue's unique key refuses it at the database, so a job that died after queueing cannot double-report |
| TC-7 | A caller omits `failed_count` | `TypeError` at the call site. There is no default, because a defaulted zero is how a run that failed 87 times reports success |
| TC-8 | A utility edits the template down to *"Bulk action completed."* | Refused at save — `{failed_count}` is non-removable class content |
| TC-9 | A scheduled job with **no signed-in user** queues a summary | Refused by name carrying **OQ-261**. No recipient is guessed; picking the tenant's first System Admin would answer an open question in code for every utility on the platform |
| TC-10 | Clerk B holds the id of Clerk A's message and marks it read | Refused, and A's message is still unread. The same answer for "no such message" and "somebody else's", so ids cannot be enumerated |
| TC-11 | `GET /in-app-messages` | Badge and list in ONE response — a count fetched separately from the list it counts can disagree with what is on screen — carrying the note that email/SMS/print still have no adapter |
| TC-12 | Resolve `…/in-app-messages/send` and `…/test-send` | `Resolver404`. **In-app is the first channel where such a route would actually have delivered something**, which is why the absence is asserted rather than assumed |
| TC-13 | A Billing Clerk reads their own inbox | 200. The permission matrix governs the TENANT'S data; a clerk who cannot read the summary of the run they started is the failure BR-NOT-020 exists to prevent |
| TC-14 | The shell renders | It PASSES `bellItems` — from the server read, not a placeholder — and both read actions. DEF-232: the bell had been dead UI since 2026-08-09 |
| TC-15 (iso) | Lone Star Ridge's in-app messages with Brazos Bend's `app.tenant_id` set | Invisible, and a cross-tenant WRITE is refused. Every row holds a rendered body naming how many accounts a utility billed and how many failed |

**4 · UX Notes** — the bell is the shell's own (BR-SHL-007: newest-first, badge capped at
**9+**). The popover line COLLAPSES the message body and never truncates it: the failure
count is at the END and is the part a clerk must see, so a `…` would cut off exactly the
number BR-NOT-020 exists to deliver. **No deep link yet** — the subject of a bulk summary
is a RUN and no screen in this product shows one, so navigating somewhere plausible would
be worse than not navigating.

**5 · Data** — `in_app_messages` (tenant · user · outbound_message · subject · body ·
`read_at`), and one new nullable column on the queue, `outbound_messages.render_context`,
which is BR-NOT-012's own *"stored render context for non-invoice notices"*. **An
invoice's figures do not go in it.**

**6 · Dependencies** — US-NOT-001 (the queue), US-NOT-002 (the dispatcher that delivers
it), US-NOT-003 (the seam its adapter sits behind), US-NOT-004 (the dispatch config),
US-NOT-006 (the template registry the summary renders from), US-NOT-017 (the rule
catalogue whose `in_app` entry this changes).

**7 · Out of scope** — offering in-app as a togglable channel on the SET-12 **staff
events** (the surface exists; the ADDRESSEE is **OQ-261**) · wiring a bill run, import or
reconciliation to call the summary (no staff event has a trigger — BR-NOT-018, OQ-262) ·
`delivered` and `bounced` on any channel, in-app included (BR-NOT-013: a third party's
confirmation and a third party's webhook, and a local adapter is not a third party).

**8 · Open Questions** — **OQ-261** (who else receives a staff notification), raised and
never answered: the two writers that exist address the person who pressed the button.
