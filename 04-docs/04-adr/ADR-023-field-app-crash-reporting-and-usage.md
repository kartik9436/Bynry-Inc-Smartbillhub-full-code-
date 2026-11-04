# ADR-023 — Crashlytics for crashes, PostHog for use (AD-18 as amended)

- **Status:** **Accepted AS AMENDED.** The design's AD-18 chose Sentry for crashes; **that half is SUPERSEDED — PO 2026-10-21 chose Crashlytics** (*"B. Crashlytics (Work page; free, Google)"*; decision log 2026-10-21, *"Field app: crash reporter, technician identity in analytics, and the web field app's future"* (1)). PostHog for usage events is unchanged.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-18**. Change request `CR-187-BRC10`.

## Context
A defect on a handset in a van must be visible to us without the technician reporting it. The design disagreed with itself: the *Work to be done* page (T-73) said Crashlytics, the *Decisions* page (AD-18) said Sentry; the PO ruled.

## Decision
**Firebase Crashlytics** for crashes — it writes its report to disk at crash time and sends on the next start. **PostHog** for events, funnels and feature flags. Both queue locally — a third queue that always yields to the outbox and the photo queue (R67). A flag read carries a cached default so an offline handset behaves the same way twice (R71). Measured: app start, the day pull, a batch send, a photo upload.

## What it reverses
The design's AD-18 crash half (*"Sentry for JavaScript errors and native crashes with source maps … Crashlytics is native-crash-first and its JavaScript story is weaker"*) — superseded by the PO's choice. No signed rule.

## Why
PO's choice: free, and the *Work to be done* page already named it. Flags matter because an app-store review takes days; without them a held feature cannot be released without shipping a build — which is also how a hold quietly rots.

## Evidence
CLAUDE.md law 14: a silently ignored flag was found only by measuring the wall clock. The design's own argument for Sentry — JavaScript faults outnumber native ones — is the thing to watch: JavaScript errors need explicit reporting into Crashlytics, so the scrubber test (ADR-024) must cover a JavaScript error as well as a native crash.

## Cost
A third offline queue; Google (Firebase) as a processor of crash data, which carries no customer fact (ADR-024).
