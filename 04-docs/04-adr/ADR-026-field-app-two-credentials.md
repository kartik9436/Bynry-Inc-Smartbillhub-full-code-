# ADR-026 — Two credentials, not one — an expiring token never stops the work

- **Status:** **Accepted as the design (R113, derived). NEEDS A SERVER ENDPOINT THAT DOES NOT EXIST YET**, and sign-off of the model and its 36-hour figure is `OQ-FLD-12798`. Addendum in B3 (`04-docs/02-decisions/03-tenancy-and-security.md`).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-21**. Change request `CR-187-BRC10`.

## Context
Dana signs in at 07:30 and drives into a valley. Her token expires at 08:30 with nine hours of work left and no signal. Treating that as *signed out* loses the day; extending the token to cover the shift leaves a credential on a handset for twelve hours.

## Decision
A **one-hour access token** that authorises talking to the server, and a **36-hour device-bound capture credential** that authorises writing locally and signs each item. The server checks the signature against the device registration. **Expiry blocks sending, which is already asynchronous — never capture.** The tenant is resolved from the credential and never read from the payload (R127).

## What it reverses
Nothing signed.

## Why
There is no state in which captured work is discarded to resolve an auth problem.

## Evidence
Walkthrough E2E-02 and E2E-21 depend on it; `TechnicianDevice.token` exists on the server today.

## Cost
One or two columns on `TechnicianDevice`, an issue/renew endpoint and per-item signature checking — named on the Security page as a precondition rather than discovered in week three.
