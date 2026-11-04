# ADR-012 — iOS Critical Alerts need Apple's permission, applied for before code

- **Status:** **Accepted and DONE** — the entitlement is granted (PO 2026-10-21, *"we have taken this permission"*; `CR-187-BRC10` §4, T-01).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-07**. Change request `CR-187-BRC10`.

## Context
An emergency (a gas odour) must reach a technician whose handset is locked and on silent.

## Decision
Apply for Apple's Critical Alerts entitlement in parallel with design. It is needed **only** to break through silent mode and Focus — a standard push already shows on a locked screen and custom sounds work on both platforms. **Android:** notification channels carry custom sound and vibration per kind; DND override is a channel permission.

## What it reverses
Nothing.

## Why
It is the one item that cannot be compressed by working harder: Apple restricts the entitlement to genuinely life-, safety- or emergency-critical apps and it must be in the provisioning profile; review takes days to weeks.

## Evidence
Walkthrough E2E-22 (emergency on a locked phone) could not pass without it; with the entitlement granted it can.

## Cost
An Apple review cycle; a provisioning profile carrying the entitlement.
