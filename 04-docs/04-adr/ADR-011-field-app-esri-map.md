# ADR-011 — Esri supplies the field app's map

- **Status:** **Accepted — already ruled 2026-10-04** (`OQ-WRK-12787` CLOSED, PO: *"Do not ask about this again."*).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-06**. Change request `CR-187-BRC10`.

## Context
The field app shows stops and a route on a map.

## Decision
Esri street tiles through the tenant's integration policy, one map only — stops and route, **no asset-network layer in v1**.

## What it reverses
Nothing.

## Why
One tile provider across the product; no account, no key, no new environment variable.

## Evidence
The utility-native reference app runs on Esri too; the Assets map already uses Esri's public street tiles.

## Cost
The map needs a signal (ADR-009); offline maps are out of scope (Walkthrough §5).
