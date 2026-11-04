# ADR-025 — Meter reading is a mode of the same app, with its own screens

- **Status:** **Accepted** — rule R73, PO ruled: *"Reading is a mode of the app, never a second app."*
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-20**. Change request `CR-187-BRC10`.

## Context
Reading a route is hundreds of repetitions, one-handed and sequence-driven — unlike working a job.

## Decision
One app, two modes. Meter reading gets its own screens inside the field app — **RW-01…RW-29**, not `MR-` (that prefix is the Meter Reads blueprint's own 53 specifications). FF-20 Readings stays — a reading inside a job, like a meter exchange's final read. **The unit of work is the address, not the meter**, because walk order is held per premises: the walk lists stops and a stop holds every meter at it.

## What it reverses
Nothing.

## Why
The ICP is 10 to 20 staff. A 3,000-account utility has no dedicated meter readers — the same person reads on Monday and fixes a leak on Tuesday (PO confirmed). Two apps is two sign-ins, two sync engines and two things to install.

## Evidence
The Meter Reads blueprint covers 19 office addresses and says *"the absence of a phone drawing is a property of the document and not of the product"* — so the reading screens were designed fresh, and nothing contradicted them.

## Cost
29 more screens in one app; one sign-in, one outbox, one photo queue, one local store.
