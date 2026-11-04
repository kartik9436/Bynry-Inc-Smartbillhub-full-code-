# ADR-021 — The web field app is kept during the build; what happens to it after is decided once the native app is built

- **Status:** **Accepted for the build period. The design's "then retired" is AMENDED: T-72 is DEFERRED** — PO 2026-10-21, verbatim: *"once native app is build after that we will decide waht to do"* (decision log 2026-10-21, *"Field app: crash reporter, technician identity in analytics, and the web field app's future"* (3)). Deferred with that trigger, not open-ended, and not an open question.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-16**. Change request `CR-187-BRC10`.

## Context
The staff app shows Field Technicians an *Open the field app* button (`FieldAppNotice`) pointing at the web field app.

## Decision
Keep the web field app (`07-frontend/src/features/work/mobile/`) live and untouched during the build. Once the native app is built, the PO decides retire or keep as a fallback (T-72). Whatever is decided, the button is repointed to the app stores in the change that ships the native app (decision log 2026-10-21, conflict 9).

## What it reverses
Nothing signed. It amends the design's own AD-16, which read *"retire it once the native app ships"*.

## Why
The day the native app ships, that button quietly leads to the wrong place — hard-won law 2's live screen behind a dead control.

## Evidence
CLAUDE.md law 2: *"when you write a hold, write the test that fires when the hold expires, in the same commit."*

## Cost
Two field apps exist side by side until T-72 is decided; the hold gets a test asserting where the button points.
