# ADR-016 — Built for gloves, not for a desk — the touch standard

- **Status:** **Accepted — RATIFIED as B14 rule 45**; rules R38 and R39 PO ruled.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-11**. Change request `CR-187-BRC10`.

## Context
Technicians wear gloves and work in weather.

## Decision
Primary action **56pt** · any interactive control **48pt** · icon-only button **48pt** · **8pt** clear between adjacent targets. **A technician taps, never types:** choice chips over text fields, a stepper over a number field, Play buttons to hear a sound rather than read its name, dictation beside every note. Forgot-password has no input box at all.

## What it reverses
The 44pt minimum used on the design's first 45 boards — that is the desk number, not the field one. No signed rule.

## Why
R39 (PO ruled): *"Built for gloves and weather."* R38 (PO ruled): *"A technician taps, never types."*

## Evidence
Walkthrough E2E-24 walks the app in sunlight, outdoors, with gloves, on the cheapest handset the utility issues.

## Cost
Fewer controls per screen; the native kit's tests assert 56/48/8.
