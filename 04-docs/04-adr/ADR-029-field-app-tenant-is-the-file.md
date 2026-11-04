# ADR-029 — Scoping the handset database: the tenant is the file, the technician is a column

- **Status:** **Accepted** — rules R131–R134, PO ruled. **Supersedes rule R114** (*"Every local table carries tenant_id"*, tagged *Repo*) and the matching sentence on the design's Security page §3.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-24**. Change request `CR-187-BRC10`.

## Context
A handset may be shared by several technicians, and a contractor may work for two utilities.

## Decision
One SQLite file per tenant — `field-<tenant>.sqlite`, chosen at sign-in — and `technician_id NOT NULL` on the ten tables that hold work (`work_order`, `wo_item`, `wo_reading`, `route`, `route_stop`, `route_read`, `outbox`, `photo`, `activity`, `crew_time`). The sync watermark is per technician per table (R134). Reference data (`premise`, `customer`, `asset`, `document`, `work_order_templates`) is not scoped — it is reached only by join from a scoped row, and an address lives in one place.

## What it reverses
R114 / Security §3's *"Every table carries tenant_id and every query names it"* — a claim, not a design: no table in the inventory carried it.

## Why
A tenant column would ask nineteen tables and some two hundred reads each to remember the filter; a separate file makes a cross-tenant read impossible rather than unlikely — the reasoning the server uses for forced row-level security. A per-technician file would hide the previous technician's unsent work, which must stay and send under their name.

## Evidence
It fixes two faults that were in the design and would have shipped: the next person to sign in seeing the previous one's jobs, and one technician's pull advancing another's watermark so deltas are lost with nothing raising.

## Cost
Zero tenant columns. **The real deliverable is one scoped-query helper and a test that fails any statement reaching a scoped table without it (R133).**
