# ADR-020 — Asset types stay configurable

- **Status:** **Accepted** — rule R15, PO ruled.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-15**. Change request `CR-187-BRC10`.

## Context
Today the field app works on meters and sub-meters; linear assets (mains, poles, valves) are *"in future, yes"*.

## Decision
Meters and sub-meters only today. But the screen is called **Asset**, the type list is data, the map can draw a line, and nothing assumes one asset is one point.

## What it reverses
Nothing.

## Why
The instruction is negative: build nothing now that has to be ripped out later — the same doctrine the product runs on for tenant size (`NFR-5`).

## Evidence
R15: *"Assets are meters and sub-meters only, for now. No linear assets. But nothing is built that forbids them later."*

## Cost
None now.
