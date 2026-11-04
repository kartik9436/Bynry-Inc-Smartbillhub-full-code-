# ADR-018 — Pushed screens, not stacked overlays

- **Status:** **Accepted** (design decision).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-13**. Change request `CR-187-BRC10`.

## Context
The reference app opens panels over the job.

## Decision
Native push and back, not a sticky drawer of panels that open over the job.

## What it reverses
Nothing.

## Why
The reference app's pattern leaves a technician three layers deep with three close buttons and no breadcrumb. Native back is one gesture and already muscle memory.

## Evidence
The design's job boards (FF-15 onward) are each a full pushed screen.

## Cost
A screen per step; every screen needs an inbound route (R98/R99 — the doors test).
