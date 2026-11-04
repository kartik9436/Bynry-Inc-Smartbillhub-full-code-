# ADR-008 — Almost no web front-end code ports to the field app — the design does

- **Status:** **Accepted — corrects an earlier estimate** in the design conversation.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-03**. Change request `CR-187-BRC10`.

## Context
The web field app holds an offline store, an outbox and photo handling that look reusable.

## Decision
The existing `07-frontend/src/features/work/mobile/` is a **reference implementation to re-derive from, not code to port.**

## What it reverses
An earlier estimate in the design conversation that ~80 KB of front-end engine would be kept. No signed rule.

## Why
IndexedDB, canvas image encoding, `navigator.geolocation` and the service worker are all web APIs. The schema, the per-technician capture-token model and the best-fix GPS logic port; the implementations do not.

## Evidence
The design's *Stack* page marks `offlineStore.ts` *Re-derived* and `work-mobile-sw.js` (5,817 bytes) and `work-mobile.webmanifest` *Retired*.

## Cost
Every engine piece is written again in `field-app/src`, against the same contract.
