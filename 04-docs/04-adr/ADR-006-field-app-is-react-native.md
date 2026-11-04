# ADR-006 — The field technician app is a cross-platform native app (React Native), not a web app

- **Status:** **Accepted — supersedes a signed rule.** `BR-WRK-045` SUPERSEDED 2026-10-21 by `CR-187-BRC10` (decision log 2026-10-21, *"The native field app (React Native) lives in this repo"*, PO: *"this is correct and i want to handle it as per your suggestion"*).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-01**. Change request `CR-187-BRC10`.

## Context
Field technicians and meter readers work a whole shift offline, in gloves, on shared handsets, and must hear an emergency through silent mode. The existing field app is a web app (`07-frontend/src/features/work/mobile/`) built under a signed rule that said it must be one.

## Decision
React Native. One codebase, shipped to the Android and iOS app stores. Offline-first. **Not a PWA and not a WebView shell.** It lives in `field-app/` at the repo root with its own `package.json`, lockfile and Expo/EAS build (decision log 2026-10-21, *"The native field app's folder is `field-app/`"*).

## What it reverses
`BR-WRK-045`, CONFIRMED 2026-09-05: *"The phone is a WEB APP — installable, offline-first — not a native shell."* **Now SUPERSEDED by `CR-187-BRC10`** (2026-10-21). That rule's accepted cost — *"no background push while the app is closed on some phones"* — is retired with it.

## Why
Requirement 13 (emergency alerting) cannot be built on a PWA. iPhone web push has no custom sound and Safari implements no vibration API, so an emergency alert would be silent on half the fleet.

## Evidence
The utility-native reference app the design was measured against positions on mobile-native three separate times and ships no PWA.

## Cost
App-store releases, a native build pipeline, two store listings, and an over-the-air update strategy for the JavaScript layer (design tasks T-56, T-57).

## Notes
The Apple Critical Alerts entitlement this depends on (ADR-012) was granted before code started — PO 2026-10-21, *"we have taken this permission"* (`CR-187-BRC10` §4, T-01).
