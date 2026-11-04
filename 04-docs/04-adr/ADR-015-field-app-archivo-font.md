# ADR-015 — Archivo is the font, deliberately

- **Status:** **Accepted — PO ratified 2026-10-20** (*"our style's font"*). Closes `OQ-272` part (a); part (b), web self-hosting, stays open and was not asked.
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-10**. Change request `CR-187-BRC10`.

## Context
React Native ships the font file inside the app bundle.

## Decision
Archivo, bundled into the app (`@expo-google-fonts/archivo`). Open licence, so embedding is permitted.

## What it reverses
Nothing signed — it closes `OQ-272`, open since the first week: *"NOBODY HAS EVER CHOSEN THE ARCHIVO WEBFONT."*

## Why
On the web the choice could be dodged with a font link. Building the app would have ratified it by accident (hard-won law 1: the token file claimed it was decided, and it was decided by nobody).

## Evidence
`OQ-272` row in `12-governance/01-open-questions.md`; `CR-187-BRC10` §4, T-03.

## Cost
None beyond the bundle size of the font files.
