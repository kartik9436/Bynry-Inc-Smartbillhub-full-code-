# ADR-022 — The handset database is SQLite, not a document store

- **Status:** **Accepted.** Rests on R52 (derived) and R130 (PO ruled: one `wo_item` table with a kind).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-17**. Change request `CR-187-BRC10`.

## Context
The handset holds about twenty tables and the capture queue (the design's *Mobile data* page).

## Decision
SQLite for the tables and the capture queue. MMKV for the handful of preferences. Nothing else. **Photographs are files on disk, never blobs in the database** — the table holds a path.

## What it reverses
Nothing.

## Why
The data is relational — an order has tasks, tasks have photographs, an asset has sub-meters — and the server is PostgreSQL, so mirroring its shape removes a class of translation bug. A document store would move the joins into JavaScript, and the capture queue needs real transactions: a reading, its photograph row and its idempotency key land together or not at all.

## Evidence
The queries the app runs are joins with ordering over up to 1,000 rows a day on a mid-range Android handset. Thirty-eight photographs a day as blobs would slow every query for no benefit.

## Cost
A schema with a versioned wire-to-local mapping (R117).
