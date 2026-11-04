# ADR-027 — One landing screen above both modes: what is left and what is next

- **Status:** **Accepted as drawn, with a collision OPEN.** It collides with rule R102 (PO ruled: *"Two tabs, Jobs and Reads"*) — `OQ-FLD-12799`. Whether a speed view may ever exist is `OQ-FLD-12794`.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-22**. Change request `CR-187-BRC10`.

## Context
Reads became a mode (ADR-025) after the navigation was ruled.

## Decision
A landing screen above both modes, one tile each for Jobs and Reads. **The bottom bar becomes Home · Jobs · Reads.** It shows jobs left, done, on hold and the next stop; meters left, read, could-not-be and the nearest stop; waiting to send; hours today. **It does not show** reads per hour, average job time or a ranking (R120).

## What it reverses
The navigation ruling of *"a drawer plus one or two bottom tabs"* — recorded as a change rather than assumed, and put back to the PO as `OQ-FLD-12799` because R102 is a PO ruling (law 13: a collision with a signed rule is stated, never assumed).

## Why
A technician's dashboard tells them what to do next; a performance dashboard is a different product for a different person, and it is the utility's call whether one exists.

## Evidence
Every phone drawing (e.g. `wireframes/phone/FF-10-today.png`) shows Home · Jobs · Reads.

## Cost
One more screen; the bottom bar has three tabs.
