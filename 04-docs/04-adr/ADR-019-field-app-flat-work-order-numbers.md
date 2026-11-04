# ADR-019 — Flat work-order numbers; tasks come from the template; one status model

- **Status:** **Accepted** (design decision).
- **Date:** 2026-10-21
- **Deciders:** Product Owner (rulings named below) · design author (the design conversation of 2026-10-20/21) · recorded by lane DOC-C under `CR-187-BRC10`
- **Source:** *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21, app version 2.587.0), decision **AD-14**. Change request `CR-187-BRC10`.

## Context
The reference app numbers sub-tasks and carries a status plus a sub-status.

## Decision
`WO-4822` stays flat. Tasks inside it carry the template's own ids — no second numbering level. One status model: the repository's three orthogonal axes (state, outcome, dispatch state).

## What it reverses
Nothing.

## Why
The three axes are better factored than a status plus sub-status. A field-raised order gets no number until it syncs (R24, PO ruled), which a flat series makes simple.

## Evidence
The seven dispatch states are signed (`BR-WRK-023`); R106 (PO ruled) invents no eighth.

## Cost
None.
