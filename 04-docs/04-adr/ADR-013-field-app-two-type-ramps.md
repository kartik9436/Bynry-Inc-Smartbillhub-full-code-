# ADR-013 — One UI standard, two type ramps — the phone has its own text sizes

- **Status:** **Accepted — RATIFIED as B14 rule 45** (PO 2026-10-20/21; written as Phase 0 task T-04).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-08**. Change request `CR-187-BRC10`.

## Context
The web standard's type anchors were measured in a browser at 1280 and 1440.

## Decision
Same colours, same spacing scale, same font, same rules. One set of text sizes for the web, a second for the phone. **Native ramp:** screen title **22** (web 32) · section head **17** (web 20–25) · body **15** (unchanged) · label **13** (unchanged) · micro **12** (web 11, raised for daylight).

## What it reverses
Nothing on the web: B14 rule 40's 32px page head still holds on every web screen. Rule 45's scope is `field-app/` only.

## Why
A 32px title on a 390pt phone wraps to three lines and pushes the work below the fold. **Not two systems**, because two design systems in one product is the repository's own named *"most expensive recurring fault"*.

## Evidence
B14 rule 45 (`04-docs/02-decisions/14-ui-conventions.md`).

## Cost
Both ramps live side by side in `shared/tokens.ts` (B13 §7); the native kit's tests assert 22/17/15/13/12.
