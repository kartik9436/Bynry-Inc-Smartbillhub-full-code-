# Module — notifications

Outbound comms via tenant-connected mailbox (BYO email — Google/M365 OAuth or SMTP), SMS/print/e-sign seams.

**Owns (B2):** notification_templates, notifications — extended by **`outbound_messages`, the PLATFORM-WIDE outbound queue** (B2 r12 #16, BR-NOT-005): one table for email + SMS + print across ALL modules; module writers insert (the reviewed interface), ONLY the notifications dispatcher sends. Exact DDL disposition of the base `notifications` table vs `outbound_messages` = Eng-Lead 🔒 (see field-map discrepancy N-6).
**Screens:** cross-cutting (A15 matrix) · S8 Settings → Notifications tab = the delivery/dispatch home (BR-TEN-041 #8) · designers S94–S96 (disconnect/dunning/receipt printable), S97–S102 (email), S103–S106 (SMS), S67 (contracts group — 4 types per BR-NOT-004) · S91–S93 bill/statement designers are billing-owned (US-BIL-021).
**Boundary rule (B1):** no other module writes this module's tables — EXCEPT the sanctioned `outbound_messages` insert interface (r12 #16); cross-module reads via service functions only (US-NOT-015).

**v4 update (r8/r9):** 16 document & message templates with designers (S91–S106) under Settings → Reference data; merge-variable catalog; versioned + audit-logged. See A19 v4 + A13.

## Pack status (2026-08-09)
**15 stories · 4 epics authored** — see [`05-user-stories.md`](05-user-stories.md).
- **EP-NOT-01** the platform outbound queue + dispatcher + channel seam + dispatch-home config (W3 — billing/payments queue-writers depend on it).
- **EP-NOT-02** template designers & rendering engine: merge catalogs, version lifecycle draft→published→archived, pinning + undeletable-pinned for every designer S91+ (A19 addendum b), category assignment (W3).
- **EP-NOT-03** notice generation (disconnect tiers + certified final + medical-hold exclusion), tone→tier reminder rendering, receipts + plan notices, S67 contracts (W4).
- **EP-NOT-04** delivery ops: platform dashboard + re-queue, bounce/returned-mail → bad-address flow, report feeds + W6 email consumers (W4/W5).

**The spine (BR-NOT-005):** every email/SMS/print from any module is a queue row FIRST; the dispatcher sends in tenant-config batches (default 500) at provider pace; statuses queued→sent→delivered|failed|bounced; retry ×3 backoff; per-run dashboard + re-queue. Print/PDF live v1; email dispatch W6 (OQ-073/074 closed — BYO mailbox small tenants, transactional ESP volume); SMS v1.1 (Twilio seam).

## ⚠ WHERE THE CHAIN ACTUALLY ENDS IN THIS RELEASE (PO ruling 2026-08-15 → BR-NOT-013)
**Issuing a bill does NOT mean the customer receives one. Delivery is OUT of this release, by decision** — no provider adapter exists or is coming on ANY channel, **print included**. Read the spine above with that in mind: rows are written, pinned and RENDERED, the dispatcher reaches the provider boundary, and there it **reports the adapter's absence by name and stops**. That is correct output, not a defect, and no lane is to build or fake an adapter to make a test green (BR-NOT-013 carries the full rule and its two consequences; `10-scripts/gates/seam_known_gaps.txt` marks both provider seams ACCEPTED rather than owed).

Two statuses in the spine's list are therefore **unreachable on this deployment**: `delivered` and `bounced` are provider facts and nothing in the repo can write either. They must render as **NOT REPORTED**, never as zero.

## Build state, 2026-08-15 (W3/W4 content lane)
Delivery core (US-NOT-001/002/003/004/005) landed earlier the same day. This lane added the **document-content half**: the template store and its lifecycle (**US-NOT-006** — `notification_templates` + `notification_template_versions`, migrations 0005/0006, which is what made ANY render possible; before it `render_for_dispatch` refused every row), **disconnect + dunning generation** (US-NOT-009/010, `apps/notifications/notices.py`), **delivery ops** (US-NOT-013/014/015, `apps/notifications/delivery_ops.py` + migration 0007 — the dashboard read-model, re-queue, returned mail, paper holds) and **custom-field variables** (US-NOT-016, in the renderer). Still unbuilt in this module: **US-NOT-007/008** designer surfaces, **US-NOT-011** receipts/plan-notice consumption, **US-NOT-012** contract generation — and thirteen template classes cannot have a body saved at all until **OQ-206**/**OQ-207** are answered, because no signed document gives them a merge-variable catalog.
