# ADR-014 — Three themes from one token set: light, dark and sunlight

- **Status:** **Accepted** (design decision).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-09**. Change request `CR-187-BRC10`.

## Context
Technicians work in basements, at night, and in direct sun.

## Decision
**Light** (default) · **Dark** (basements and night) · **Sunlight** (maximum contrast: pure white, black text, 2–3px borders, one size up). All three derive from the one token set.

## What it reverses
Nothing.

## Why
Dark and sunlight are not inverses of each other. Dark lowers light output; sunlight raises contrast.

## Evidence
The phone boards include the theme switch (`04-docs/05-modules/18-field-app/wireframes/`).

## Cost
Every native component is checked in three themes.
