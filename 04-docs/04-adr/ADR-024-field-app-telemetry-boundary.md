# ADR-024 — Telemetry carries no customer data and records no screen; the technician MAY be named

- **Status:** **Accepted AS AMENDED.** Rules R66 and R68 stand. **R69 and the design's identity clause are REVERSED — PO 2026-10-21: usage data MAY name the individual technician** (*"B. Yes, by name"*; decision log 2026-10-21, *"Field app: crash reporter, technician identity in analytics, and the web field app's future"* (2)).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-19**. Change request `CR-187-BRC10`.

## Context
Crash reports and analytics leave the handset for a third party.

## Decision
Every event and breadcrumb passes a scrubber built as an **allow list of fields**, not a block list. **Never sent — unchanged by the ruling:** a CUSTOMER's name, address, account number, balance, reading value, photograph, signature — and never an outbox payload. **Session replay off** — not configured carefully, off. **Identity:** tenant, role and **the technician** — the technician's own identity is allowed; the customer's never is.

## What it reverses
The design's *"Identity: tenant, role and an anonymous device id … the build assumes not until ruled otherwise"* (AD-19), rule R69, and Security §6 *"No analytics identity per person … Pending your word"*. Worked figure shown to the PO: *"Disconnect jobs take 9 minutes longer than planned"* is fine either way; *"Marco is the slowest"* is only possible with a yes.

## Why
A replay of a technician's screen records customer names, addresses, balances and signatures, so replay stays off whatever the identity ruling. The utility owns its workforce question and the PO answered it.

## Evidence
Security §7.5: a test that forces a crash on FF-25 Customer with a real account on screen and asserts the report carries no name, address, account or balance. Design task T-74 builds the scrubber before any screen that shows a customer.

## Cost
**Not the audit trail:** `audit_log` on the server is the record; nobody may later reach for analytics to answer a question about a payment.
